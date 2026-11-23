from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from hostels.models import University, Hostel, Warden
from rooms.models import RoomCategory, Room, Bed, RoomPricing
from students.models import Student
from allocations.models import BedAllocation
from exchanges.models import PolicyRule, ExchangeRequest, ExchangeProposal, ProposalParticipant
from exchanges.services import (
    create_direct_proposal, student_accept_proposal,
    student_decline_proposal, validate_student_eligibility,
    ExchangeMatchingEngine
)
from approvals.models import WardenApproval
from approvals.services import warden_approve_proposal, warden_reject_proposal
from exchanges.execution import execute_exchange_atomic
from finance.models import StudentAccount, TransferRecord
from notifications.models import Notification

User = get_user_model()

class ComprehensiveExchangeAndWardenTests(TestCase):
    """
    Detailed test suite verifying:
    1. Direct exchange between students in the SAME hostel.
    2. Direct exchange between students in DIFFERENT hostels (Cross-hostel).
    3. Multi-party 3-student cyclic rotation.
    4. Policy enforcement: Cross-gender exchange blocked.
    5. Policy enforcement: Disciplinary hold & Fee hold blocked.
    6. All-or-Nothing safety: One rejection cancels the entire proposal without bed mutation.
    7. Warden features: Dashboard, Approvals Queue, Occupancy Grid, Residents Directory, Broadcast Messages.
    """

    def setUp(self):
        # 1. Exchange Policy
        self.policy = PolicyRule.get_current()
        self.policy.max_cycle_length = 5
        self.policy.allow_cross_hostel = True
        self.policy.allow_cross_category = True
        self.policy.save()

        # 2. University & Hostels
        self.univ = University.objects.create(name='National University', code='NUNIV')
        self.hostel_a = Hostel.objects.create(name='Boys Hostel A', code='BHA', gender='Male', university=self.univ)
        self.hostel_b = Hostel.objects.create(name='Boys Hostel B', code='BHB', gender='Male', university=self.univ)
        self.hostel_girls = Hostel.objects.create(name='Girls Hostel A', code='GHA', gender='Female', university=self.univ)

        # 3. Categories & Pricing
        self.cat_single = RoomCategory.objects.create(name='AC Single', is_ac=True, capacity=1)
        self.cat_double = RoomCategory.objects.create(name='Non-AC Double', is_ac=False, capacity=2)
        RoomPricing.objects.create(hostel=self.hostel_a, category=self.cat_single, academic_year='2026-2027', annual_fee=Decimal('90000.00'))
        RoomPricing.objects.create(hostel=self.hostel_a, category=self.cat_double, academic_year='2026-2027', annual_fee=Decimal('60000.00'))
        RoomPricing.objects.create(hostel=self.hostel_b, category=self.cat_single, academic_year='2026-2027', annual_fee=Decimal('90000.00'))

        # 4. Wardens
        self.warden_user_a = User.objects.create_user(username='warden_a', password='HostelX@2026', role=User.Role.WARDEN)
        self.warden_a = Warden.objects.create(user=self.warden_user_a, hostel=self.hostel_a, is_chief=False)

        self.warden_user_b = User.objects.create_user(username='warden_b', password='HostelX@2026', role=User.Role.WARDEN)
        self.warden_b = Warden.objects.create(user=self.warden_user_b, hostel=self.hostel_b, is_chief=False)

        self.chief_warden_user = User.objects.create_user(username='chief_warden', password='HostelX@2026', role=User.Role.CHIEF_WARDEN)
        self.chief_warden = Warden.objects.create(user=self.chief_warden_user, hostel=self.hostel_a, is_chief=True)

        self.client = Client()

    def _create_resident_student(self, username, full_name, gender, hostel, category, room_no, bed_id, fee_status='PAID', disc_status='CLEAN'):
        user = User.objects.create_user(username=username, password='HostelX@2026', role=User.Role.STUDENT)
        room, _ = Room.objects.get_or_create(hostel=hostel, room_number=room_no, defaults={'category': category, 'floor': 1})
        bed, _ = Bed.objects.get_or_create(room=room, bed_identifier=bed_id, defaults={'status': 'OCCUPIED'})
        bed.status = 'OCCUPIED'
        bed.save()

        student = Student.objects.create(
            user=user,
            student_id=f"ID_{username}",
            registration_number=f"REG_{username}",
            full_name=full_name,
            email=f"{username}@university.edu",
            mobile_number='9876543210',
            gender=gender,
            course='B.Tech CSE',
            academic_year='2nd Year',
            current_hostel=hostel,
            current_room=room,
            current_bed=bed,
            fee_status=fee_status,
            disciplinary_status=disc_status,
        )
        BedAllocation.objects.create(student=student, bed=bed, academic_year='2026-2027', is_active=True)
        StudentAccount.objects.create(student=student)
        return student

    # =========================================================================
    # SCENARIO 1: SAME HOSTEL EXCHANGE (Direct 2-Person Swap)
    # =========================================================================
    def test_scenario_01_same_hostel_exchange_end_to_end(self):
        """
        Student 1 (Room 101, Bed B1) and Student 2 (Room 102, Bed B1) are both in Boys Hostel A.
        Flow: Propose -> Accept -> Warden Approve -> Atomic Execution -> Beds swapped atomically.
        """
        s1 = self._create_resident_student('same_s1', 'Aarav Sharma', 'Male', self.hostel_a, self.cat_single, '101', 'B1')
        s2 = self._create_resident_student('same_s2', 'Rohan Gupta', 'Male', self.hostel_a, self.cat_single, '102', 'B1')

        bed1_orig = s1.current_bed
        bed2_orig = s2.current_bed

        # 1. Student 1 proposes direct swap
        prop, msg = create_direct_proposal(s1, s2, remarks="Same hostel room swap mutually agreed")
        self.assertIsNotNone(prop, f"Proposal creation failed: {msg}")
        self.assertEqual(prop.cycle_length, 2)
        self.assertEqual(prop.status, 'PROPOSED')

        # 2. Student 2 accepts proposal
        ok, msg2 = student_accept_proposal(prop, s2, remarks="Accepted, ready to swap beds")
        self.assertTrue(ok, f"Student acceptance failed: {msg2}")
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'PENDING_WARDEN_APPROVAL')

        # 3. Only ONE warden approval needed because both students belong to Boys Hostel A
        self.assertEqual(prop.warden_approvals.count(), 1)
        warden_appr = prop.warden_approvals.first()
        self.assertEqual(warden_appr.hostel, self.hostel_a)

        # Warden approves
        ok_w, msg_w = warden_approve_proposal(prop, self.warden_a, self.hostel_a, remarks="Approved room change within Hostel A")
        self.assertTrue(ok_w, f"Warden approval failed: {msg_w}")
        prop.refresh_from_db()
        self.assertIn(prop.status, ['APPROVED_BY_WARDENS', 'PAYMENT_PENDING'])

        # 4. Atomic Execution
        ok_exec, records = execute_exchange_atomic(prop, executed_by_user=self.warden_user_a)
        self.assertTrue(ok_exec)
        self.assertEqual(len(records), 2)

        # 5. Verify Database State
        s1.refresh_from_db()
        s2.refresh_from_db()

        # Beds are swapped!
        self.assertEqual(s1.current_bed.id, bed2_orig.id)
        self.assertEqual(s1.current_room.room_number, '102')
        self.assertEqual(s2.current_bed.id, bed1_orig.id)
        self.assertEqual(s2.current_room.room_number, '101')

        # Both remain in Boys Hostel A
        self.assertEqual(s1.current_hostel, self.hostel_a)
        self.assertEqual(s2.current_hostel, self.hostel_a)

        # Both beds remain OCCUPIED
        bed1_orig.refresh_from_db()
        bed2_orig.refresh_from_db()
        self.assertEqual(bed1_orig.status, 'OCCUPIED')
        self.assertEqual(bed2_orig.status, 'OCCUPIED')

        # Transfer records created
        self.assertEqual(TransferRecord.objects.filter(proposal=prop).count(), 2)

    # =========================================================================
    # SCENARIO 2: DIFFERENT HOSTELS EXCHANGE (Cross-Hostel Swap)
    # =========================================================================
    def test_scenario_02_different_hostels_exchange_end_to_end(self):
        """
        Student A is in Boys Hostel A, Student B is in Boys Hostel B.
        Flow: Propose -> Accept -> Multi-Warden Approvals (Hostel A & Hostel B) -> Atomic Execution.
        """
        s_a = self._create_resident_student('cross_a', 'Vikram Patel', 'Male', self.hostel_a, self.cat_single, '201', 'B1')
        s_b = self._create_resident_student('cross_b', 'Devendra Singh', 'Male', self.hostel_b, self.cat_single, '201', 'B1')

        bed_a_orig = s_a.current_bed
        bed_b_orig = s_b.current_bed

        # 1. Propose cross-hostel swap
        prop, msg = create_direct_proposal(s_a, s_b, remarks="Cross-hostel exchange to move closer to labs")
        self.assertIsNotNone(prop, msg)

        # 2. Student B accepts
        student_accept_proposal(prop, s_b)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'PENDING_WARDEN_APPROVAL')

        # 3. Exactly 2 distinct warden approvals required (one for Hostel A, one for Hostel B)
        self.assertEqual(prop.warden_approvals.count(), 2)
        hostels_to_approve = set(prop.warden_approvals.values_list('hostel__code', flat=True))
        self.assertEqual(hostels_to_approve, {'BHA', 'BHB'})

        # Warden A approves for Hostel A
        warden_approve_proposal(prop, self.warden_a, self.hostel_a, remarks="Hostel A clear")
        prop.refresh_from_db()
        # Proposal MUST still be pending because Hostel B has not yet approved
        self.assertEqual(prop.status, 'PENDING_WARDEN_APPROVAL')

        # Warden B approves for Hostel B
        warden_approve_proposal(prop, self.warden_b, self.hostel_b, remarks="Hostel B clear")
        prop.refresh_from_db()
        self.assertIn(prop.status, ['APPROVED_BY_WARDENS', 'PAYMENT_PENDING'])

        # 4. Atomic Execution
        ok_exec, records = execute_exchange_atomic(prop, executed_by_user=self.chief_warden_user)
        self.assertTrue(ok_exec)

        # 5. Verify Cross-Hostel Bed and Hostel Updates
        s_a.refresh_from_db()
        s_b.refresh_from_db()

        # S_A moved to Boys Hostel B!
        self.assertEqual(s_a.current_hostel, self.hostel_b)
        self.assertEqual(s_a.current_bed.id, bed_b_orig.id)

        # S_B moved to Boys Hostel A!
        self.assertEqual(s_b.current_hostel, self.hostel_a)
        self.assertEqual(s_b.current_bed.id, bed_a_orig.id)

    # =========================================================================
    # SCENARIO 3: MULTI-PARTY ROTATION (3-Student Cyclic Chain)
    # =========================================================================
    def test_scenario_03_multi_party_cyclic_exchange(self):
        """
        Cycle: Student 1 -> Student 2's Bed -> Student 3's Bed -> Student 1's Bed.
        Engine detects the directed cycle of length 3, generates proposal, all accept, atomic swap executes.
        """
        s1 = self._create_resident_student('cyc_s1', 'Student One', 'Male', self.hostel_a, self.cat_single, '301', 'B1')
        s2 = self._create_resident_student('cyc_s2', 'Student Two', 'Male', self.hostel_a, self.cat_single, '302', 'B1')
        s3 = self._create_resident_student('cyc_s3', 'Student Three', 'Male', self.hostel_a, self.cat_single, '303', 'B1')

        b1_orig = s1.current_bed
        b2_orig = s2.current_bed
        b3_orig = s3.current_bed

        # Requests forming a cycle: S1 wants B2, S2 wants B3, S3 wants B1
        req1 = ExchangeRequest.objects.create(student=s1, current_bed=b1_orig, specific_target_bed=b2_orig, status='ACTIVE')
        req2 = ExchangeRequest.objects.create(student=s2, current_bed=b2_orig, specific_target_bed=b3_orig, status='ACTIVE')
        req3 = ExchangeRequest.objects.create(student=s3, current_bed=b3_orig, specific_target_bed=b1_orig, status='ACTIVE')

        engine = ExchangeMatchingEngine(policy=self.policy)
        G, students_by_id, _ = engine.build_graph(active_requests=[req1, req2, req3])
        cycles = engine.find_cycles(G, max_length=3)

        self.assertEqual(len(cycles), 1)
        self.assertEqual(len(cycles[0]), 3)

        proposals = engine.generate_proposals_for_cycles(cycles, students_by_id, auto_commit=True)
        self.assertEqual(len(proposals), 1)
        prop = proposals[0]
        self.assertEqual(prop.cycle_length, 3)

        # All 3 students accept
        for s in [s1, s2, s3]:
            student_accept_proposal(prop, s)

        prop.refresh_from_db()
        self.assertEqual(prop.status, 'PENDING_WARDEN_APPROVAL')

        # Warden approves cycle
        warden_approve_proposal(prop, self.warden_a, self.hostel_a)
        prop.refresh_from_db()

        # Atomic execution of 3-way cycle
        ok, records = execute_exchange_atomic(prop)
        self.assertTrue(ok)
        self.assertEqual(len(records), 3)

        # Verify rotated beds
        s1.refresh_from_db()
        s2.refresh_from_db()
        s3.refresh_from_db()

        self.assertEqual(s1.current_bed.id, b2_orig.id)
        self.assertEqual(s2.current_bed.id, b3_orig.id)
        self.assertEqual(s3.current_bed.id, b1_orig.id)

    # =========================================================================
    # SCENARIO 4: POLICY REJECTION - CROSS GENDER EXCHANGE BLOCKED
    # =========================================================================
    def test_scenario_04_cross_gender_exchange_strictly_blocked(self):
        """
        Male student attempts to exchange room with Female student.
        Must be blocked by policy with an informative message.
        """
        s_male = self._create_resident_student('male_stu', 'Male Student', 'Male', self.hostel_a, self.cat_single, '401', 'B1')
        s_female = self._create_resident_student('female_stu', 'Female Student', 'Female', self.hostel_girls, self.cat_single, '401', 'B1')

        prop, msg = create_direct_proposal(s_male, s_female)
        self.assertIsNone(prop)
        self.assertIn("gender", msg.lower())

    # =========================================================================
    # SCENARIO 5: POLICY REJECTION - DISCIPLINARY & FEE HOLDS
    # =========================================================================
    def test_scenario_05_disciplinary_and_fee_holds_block_exchange(self):
        """
        A student on disciplinary hold or unpaid fee cannot initiate an exchange.
        """
        s_clean = self._create_resident_student('clean_stu', 'Clean Student', 'Male', self.hostel_a, self.cat_single, '501', 'B1')
        s_hold = self._create_resident_student('hold_stu', 'Hold Student', 'Male', self.hostel_a, self.cat_single, '502', 'B1', disc_status='HOLD')

        # 1. Test Disciplinary Hold
        is_eligible, reason = validate_student_eligibility(s_hold, self.policy)
        self.assertFalse(is_eligible)
        self.assertIn("disciplinary", reason.lower())

        prop, msg = create_direct_proposal(s_clean, s_hold)
        self.assertIsNone(prop)
        self.assertIn("disciplinary", msg.lower())

        # 2. Test Unpaid Fee Hold
        s_unpaid = self._create_resident_student('unpaid_stu', 'Unpaid Student', 'Male', self.hostel_a, self.cat_single, '503', 'B1', fee_status='UNPAID')
        is_eligible_fee, reason_fee = validate_student_eligibility(s_unpaid, self.policy)
        self.assertFalse(is_eligible_fee)
        self.assertIn("unpaid", reason_fee.lower())

        prop_fee, msg_fee = create_direct_proposal(s_clean, s_unpaid)
        self.assertIsNone(prop_fee)
        self.assertIn("unpaid", msg_fee.lower())

    # =========================================================================
    # SCENARIO 6: ALL-OR-NOTHING SAFETY (Decline Cancels Proposal Without Mutation)
    # =========================================================================
    def test_scenario_06_decline_cancels_proposal_safely(self):
        """
        In a proposed exchange, if one student declines, the proposal is marked REJECTED
        and zero room/bed allocations are mutated.
        """
        s1 = self._create_resident_student('dec_s1', 'Student Dec 1', 'Male', self.hostel_a, self.cat_single, '601', 'B1')
        s2 = self._create_resident_student('dec_s2', 'Student Dec 2', 'Male', self.hostel_a, self.cat_single, '602', 'B1')

        prop, _ = create_direct_proposal(s1, s2)
        ok, msg = student_decline_proposal(prop, s2, reason="Prefer current room")
        self.assertTrue(ok)

        prop.refresh_from_db()
        self.assertEqual(prop.status, 'REJECTED')

        # Check beds are NOT modified
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.current_bed.room.room_number, '601')
        self.assertEqual(s2.current_bed.room.room_number, '602')

    # =========================================================================
    # SCENARIO 7: WARDEN FEATURES TEST (All Views & Consoles Work)
    # =========================================================================
    def test_scenario_07_all_warden_features_and_consoles(self):
        """
        Verify all Warden features function properly via authenticated HTTP client:
        - Warden Dashboard (/dashboard/warden/)
        - Approval Queue (/approvals/queue/)
        - Bed Occupancy Grid (/hostels/occupancy/)
        - Residents Directory (/hostels/residents/)
        - Send Message to Students (/notifications/send/)
        """
        # Create resident students so warden has real data
        s1 = self._create_resident_student('wfeat_s1', 'Resident Alpha', 'Male', self.hostel_a, self.cat_single, '701', 'B1')
        s2 = self._create_resident_student('wfeat_s2', 'Resident Beta', 'Male', self.hostel_a, self.cat_single, '702', 'B1')

        # Create a pending proposal
        prop, _ = create_direct_proposal(s1, s2)
        student_accept_proposal(prop, s2)

        # Login as Warden A
        self.client.force_login(self.warden_user_a)

        # 1. Warden Dashboard
        res_dash = self.client.get('/dashboard/warden/')
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'Boys Hostel A')
        self.assertContains(res_dash, 'Hostel Management Console')

        # 2. Dedicated Approval Queue
        res_queue = self.client.get('/approvals/queue/')
        self.assertEqual(res_queue.status_code, 200)
        self.assertContains(res_queue, 'Exchange Approval Queue')
        self.assertContains(res_queue, prop.proposal_code)

        # 3. Warden Approves from detail page
        res_appr = self.client.post(f'/approvals/detail/{prop.id}/', {
            'action': 'approve',
            'remarks': 'Approved by Warden A via console',
            'hostel_id': self.hostel_a.id,
            'next': '/approvals/queue/'
        })
        self.assertEqual(res_appr.status_code, 302)
        self.assertEqual(res_appr.url, '/approvals/queue/')

        # Verify proposal approved
        appr_obj = WardenApproval.objects.get(proposal=prop, hostel=self.hostel_a)
        self.assertEqual(appr_obj.status, 'APPROVED')
        self.assertEqual(appr_obj.remarks, 'Approved by Warden A via console')

        # 4. Dedicated Bed Occupancy Grid
        res_occ = self.client.get('/hostels/occupancy/')
        self.assertEqual(res_occ.status_code, 200)
        self.assertContains(res_occ, 'Real-Time Bed Occupancy Floor Grid')
        self.assertContains(res_occ, 'B1')

        # Filter by floor
        res_occ_floor = self.client.get('/hostels/occupancy/?floor=1')
        self.assertEqual(res_occ_floor.status_code, 200)

        # 5. Dedicated Residents Directory
        res_res = self.client.get('/hostels/residents/')
        self.assertEqual(res_res.status_code, 200)
        self.assertContains(res_res, 'Hostel Residents Directory')
        self.assertContains(res_res, 'Resident Alpha')

        # Search residents
        res_search = self.client.get('/hostels/residents/?q=Alpha')
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, 'Resident Alpha')

        # 6. Warden Broadcasts Message to Students
        res_send = self.client.get('/notifications/send/')
        self.assertEqual(res_send.status_code, 200)
        self.assertContains(res_send, 'Send Message')

        res_post_msg = self.client.post('/notifications/send/', {
            'title': 'Mandatory Floor Meeting',
            'body': 'All Floor 1 residents meet at 8 PM.',
            'recipient_id': 'all'
        })
        self.assertEqual(res_post_msg.status_code, 302)

        # Verify notifications received by students
        self.assertTrue(
            Notification.objects.filter(recipient=s1.user, title='Mandatory Floor Meeting').exists()
        )
        self.assertTrue(
            Notification.objects.filter(recipient=s2.user, title='Mandatory Floor Meeting').exists()
        )
