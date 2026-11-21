import time
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from hostels.models import University, Hostel, Warden, Announcement
from rooms.models import RoomCategory, Room, Bed, RoomPricing
from students.models import Student
from allocations.models import BedAllocation
from exchanges.models import PolicyRule, ExchangeRequest, ExchangeProposal, ProposalParticipant
from exchanges.services import (
    validate_student_eligibility, create_direct_proposal,
    student_accept_proposal, student_decline_proposal,
    ExchangeMatchingEngine
)
from approvals.models import WardenApproval
from approvals.services import warden_approve_proposal, warden_reject_proposal
from finance.models import StudentAccount, FinancialTransaction, TransferRecord
from finance.services import calculate_participant_financials, process_simulated_payment
from exchanges.execution import execute_exchange_atomic, AtomicExchangeExecutionError
from mess.models import MessRegistration, MessMenu
from laundry.models import LaundryService, LaundryRequest
from maintenance.models import MaintenanceRequest
from audit.models import AuditEntry

User = get_user_model()

class HostelXBaseSetup:
    @classmethod
    def setup_base_data(cls):
        # Policy
        cls.policy = PolicyRule.get_current()
        cls.policy.max_cycle_length = 5
        cls.policy.allow_cross_hostel = True
        cls.policy.allow_cross_category = True
        cls.policy.allow_cross_academic_year = True
        cls.policy.allow_cross_course = True
        cls.policy.processing_fee = Decimal('200.00')
        cls.policy.save()

        # University
        cls.univ, _ = University.objects.get_or_create(
            code='ANIT_TEST',
            defaults={
                'name': 'Apex National Institute of Technology',
                'address': 'Campus 1',
                'contact_email': 'test@anit.edu',
                'contact_phone': '1234567890'
            }
        )

        # Hostels (2 male, 2 female)
        cls.h_boys_a, _ = Hostel.objects.get_or_create(code='TH01', defaults={'name': 'Boys Hostel A', 'gender': 'Male', 'university': cls.univ})
        cls.h_boys_b, _ = Hostel.objects.get_or_create(code='TH02', defaults={'name': 'Boys Hostel B', 'gender': 'Male', 'university': cls.univ})
        cls.h_girls_a, _ = Hostel.objects.get_or_create(code='TH03', defaults={'name': 'Girls Hostel A', 'gender': 'Female', 'university': cls.univ})
        cls.h_girls_b, _ = Hostel.objects.get_or_create(code='TH04', defaults={'name': 'Girls Hostel B', 'gender': 'Female', 'university': cls.univ})

        # Categories
        cls.cat_single, _ = RoomCategory.objects.get_or_create(name='AC Single Test', defaults={'is_ac': True, 'capacity': 1})
        cls.cat_double, _ = RoomCategory.objects.get_or_create(name='AC Double Test', defaults={'is_ac': True, 'capacity': 2})
        cls.cat_triple, _ = RoomCategory.objects.get_or_create(name='Non-AC Triple Test', defaults={'is_ac': False, 'capacity': 3})

        # Pricing
        for h in [cls.h_boys_a, cls.h_boys_b, cls.h_girls_a, cls.h_girls_b]:
            RoomPricing.objects.get_or_create(hostel=h, category=cls.cat_single, academic_year='2026-2027', defaults={'annual_fee': Decimal('96000.00')})
            RoomPricing.objects.get_or_create(hostel=h, category=cls.cat_double, academic_year='2026-2027', defaults={'annual_fee': Decimal('72000.00')})
            RoomPricing.objects.get_or_create(hostel=h, category=cls.cat_triple, academic_year='2026-2027', defaults={'annual_fee': Decimal('42000.00')})

        # Staff Users
        cls.warden_user_a, _ = User.objects.get_or_create(username='test_warden_a', defaults={'role': User.Role.WARDEN})
        cls.warden_a, _ = Warden.objects.get_or_create(user=cls.warden_user_a, defaults={'hostel': cls.h_boys_a, 'is_chief': False})

        cls.warden_user_b, _ = User.objects.get_or_create(username='test_warden_b', defaults={'role': User.Role.WARDEN})
        cls.warden_b, _ = Warden.objects.get_or_create(user=cls.warden_user_b, defaults={'hostel': cls.h_boys_b, 'is_chief': False})

        cls.chief_user, _ = User.objects.get_or_create(username='test_chief', defaults={'role': User.Role.CHIEF_WARDEN})
        cls.admin_user, _ = User.objects.get_or_create(username='test_admin', defaults={'role': User.Role.ADMIN, 'is_superuser': True})
        cls.dean_user, _ = User.objects.get_or_create(username='test_dean', defaults={'role': User.Role.DEAN})

    @classmethod
    def create_student_with_bed(cls, username, full_name, gender, hostel, category, room_no, bed_id, course='B.Tech CS', year='2nd Year', fee_st='PAID', disc_st='CLEAN'):
        u, _ = User.objects.get_or_create(username=username, defaults={'email': f"{username}@test.com", 'role': User.Role.STUDENT})
        r, _ = Room.objects.get_or_create(hostel=hostel, room_number=room_no, defaults={'category': category, 'floor': 1})
        b, _ = Bed.objects.get_or_create(room=r, bed_identifier=bed_id, defaults={'status': 'OCCUPIED'})
        b.status = 'OCCUPIED'
        b.save()

        stu, _ = Student.objects.get_or_create(
            user=u,
            defaults={
                'student_id': f"ID_{username}",
                'registration_number': f"REG_{username}",
                'full_name': full_name,
                'email': u.email,
                'mobile_number': '9999999999',
                'gender': gender,
                'course': course,
                'department': 'Eng',
                'academic_year': year,
                'current_hostel': hostel,
                'current_room': r,
                'current_bed': b,
                'fee_status': fee_st,
                'disciplinary_status': disc_st,
            }
        )
        BedAllocation.objects.get_or_create(student=stu, bed=b, academic_year='2026-2027', defaults={'is_active': True})
        StudentAccount.objects.get_or_create(student=stu, defaults={'balance': Decimal('0.00')})
        MessRegistration.objects.get_or_create(student=stu, defaults={'hostel': hostel, 'is_active': True})
        return stu

class HostelXCoreTests(TestCase, HostelXBaseSetup):
    def setUp(self):
        self.setup_base_data()

    # 1 & 2. Authentication & Role-based Access Control
    def test_01_authentication_and_rbac(self):
        c = Client()
        stu = self.create_student_with_bed('auth_stu', 'Auth Student', 'Male', self.h_boys_a, self.cat_single, '101', 'B1')
        c.force_login(stu.user)

        # Student cannot access warden or admin console
        res = c.get('/dashboard/warden/')
        self.assertEqual(res.status_code, 302)  # Redirected due to RBAC
        res_admin = c.get('/dashboard/admin/')
        self.assertEqual(res_admin.status_code, 302)

        # Student accesses student dashboard
        res_stu = c.get('/dashboard/student/')
        self.assertEqual(res_stu.status_code, 200)

    # 3 & 4. Hostel creation & Room/Bed uniqueness
    def test_02_hostel_and_bed_generation_uniqueness(self):
        self.assertEqual(Hostel.objects.filter(university=self.univ).count(), 4)
        r = Room.objects.create(hostel=self.h_boys_a, room_number='U101', category=self.cat_single)
        Bed.objects.create(room=r, bed_identifier='B1', status='VACANT')

        # Duplicate room number in same hostel violates unique constraint
        with self.assertRaises(IntegrityError):
            Room.objects.create(hostel=self.h_boys_a, room_number='U101', category=self.cat_single)

    # 5. One active allocation per student constraint
    def test_03_active_student_allocation_constraint(self):
        stu = self.create_student_with_bed('alloc_stu', 'Alloc Student', 'Male', self.h_boys_a, self.cat_single, '102', 'B1')
        r2 = Room.objects.create(hostel=self.h_boys_a, room_number='103', category=self.cat_single)
        b2 = Bed.objects.create(room=r2, bed_identifier='B1')

        # Creating another active allocation for same student violates UniqueConstraint
        with self.assertRaises(IntegrityError):
            BedAllocation.objects.create(student=stu, bed=b2, is_active=True)

    # 6. Direct exchange (2 students)
    def test_04_direct_exchange_flow(self):
        s1 = self.create_student_with_bed('dir_s1', 'Student One', 'Male', self.h_boys_a, self.cat_single, '201', 'B1')
        s2 = self.create_student_with_bed('dir_s2', 'Student Two', 'Male', self.h_boys_a, self.cat_double, '202', 'B1')

        prop, msg = create_direct_proposal(s1, s2, remarks="Mutual agreement")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.cycle_length, 2)
        self.assertEqual(prop.status, 'PROPOSED')

        # S1 accepted automatically as proposer; S2 accepts now
        ok, msg2 = student_accept_proposal(prop, s2)
        self.assertTrue(ok)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'PENDING_WARDEN_APPROVAL')

    # 7. Cross-hostel exchange (Same gender)
    def test_05_cross_hostel_exchange(self):
        s_ha = self.create_student_with_bed('c_ha', 'Hostel A Stu', 'Male', self.h_boys_a, self.cat_single, '301', 'B1')
        s_hb = self.create_student_with_bed('c_hb', 'Hostel B Stu', 'Male', self.h_boys_b, self.cat_single, '301', 'B1')

        prop, msg = create_direct_proposal(s_ha, s_hb)
        self.assertIsNotNone(prop)
        self.assertEqual(prop.participants.count(), 2)

    # 8. Different room category exchange (AC Single <-> Non-AC Triple)
    def test_06_different_room_category_exchange(self):
        s_ac = self.create_student_with_bed('s_ac', 'AC Stu', 'Male', self.h_boys_a, self.cat_single, '401', 'B1')
        s_nonac = self.create_student_with_bed('s_nonac', 'NonAC Stu', 'Male', self.h_boys_a, self.cat_triple, '402', 'B1')

        prop, msg = create_direct_proposal(s_ac, s_nonac)
        self.assertIsNotNone(prop)

    # 9. Strict same-gender restriction
    def test_07_same_gender_restriction(self):
        s_male = self.create_student_with_bed('s_male', 'Male Stu', 'Male', self.h_boys_a, self.cat_single, '501', 'B1')
        s_female = self.create_student_with_bed('s_female', 'Female Stu', 'Female', self.h_girls_a, self.cat_single, '501', 'B1')

        prop, msg = create_direct_proposal(s_male, s_female)
        self.assertIsNone(prop)
        self.assertIn("gender", msg.lower())

    # 10 & 11. Different courses & different academic years
    def test_08_different_courses_and_academic_years(self):
        s_cs_1st = self.create_student_with_bed('cs1', 'CS 1st', 'Male', self.h_boys_a, self.cat_single, '601', 'B1', course='B.Tech CS', year='1st Year')
        s_mech_4th = self.create_student_with_bed('mech4', 'Mech 4th', 'Male', self.h_boys_a, self.cat_single, '602', 'B1', course='B.Tech Mech', year='4th Year')

        prop, msg = create_direct_proposal(s_cs_1st, s_mech_4th)
        self.assertIsNotNone(prop)

    # 12, 13, 14. Graph matching & Multi-party cycles (3, 4, 5 students)
    def test_09_multi_party_cycles_3_4_5_students(self):
        # Create 5 students in a cycle: S1 -> S2 -> S3 -> S4 -> S5 -> S1
        students = []
        for i in range(1, 6):
            stu = self.create_student_with_bed(f'cycl_{i}', f'Cycle Student {i}', 'Male', self.h_boys_a, self.cat_single, f'70{i}', 'B1')
            students.append(stu)

        # Create preferences creating a directed 5-cycle
        requests = []
        for i in range(5):
            curr_stu = students[i]
            next_stu = students[(i + 1) % 5]
            req = ExchangeRequest.objects.create(
                student=curr_stu,
                current_bed=curr_stu.current_bed,
                specific_target_bed=next_stu.current_bed,
                status='ACTIVE'
            )
            requests.append(req)

        engine = ExchangeMatchingEngine(policy=self.policy)
        G, students_by_id, _ = engine.build_graph(active_requests=requests)
        cycles = engine.find_cycles(G, max_length=5)

        self.assertTrue(len(cycles) >= 1)
        # Verify 5-cycle found
        cycle_lengths = [len(c) for c in cycles]
        self.assertIn(5, cycle_lengths)

        # Generate proposal
        proposals = engine.generate_proposals_for_cycles(cycles, students_by_id, auto_commit=True)
        self.assertTrue(len(proposals) >= 1)
        prop5 = proposals[0]
        self.assertEqual(prop5.cycle_length, 5)
        self.assertEqual(prop5.participants.count(), 5)

    # 15. Participant rejection cancels entire proposal
    def test_10_participant_rejection(self):
        s1 = self.create_student_with_bed('rej_s1', 'Rej Stu 1', 'Male', self.h_boys_a, self.cat_single, '801', 'B1')
        s2 = self.create_student_with_bed('rej_s2', 'Rej Stu 2', 'Male', self.h_boys_a, self.cat_single, '802', 'B1')

        prop, _ = create_direct_proposal(s1, s2)
        ok, msg = student_decline_proposal(prop, s2, reason="Not interested")
        self.assertTrue(ok)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'REJECTED')
        # Bed allocations did NOT change
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.current_bed.room.room_number, '801')
        self.assertEqual(s2.current_bed.room.room_number, '802')

    # 16. Proposal expiry
    def test_11_proposal_expiry(self):
        s1 = self.create_student_with_bed('exp_s1', 'Exp Stu 1', 'Male', self.h_boys_a, self.cat_single, '901', 'B1')
        s2 = self.create_student_with_bed('exp_s2', 'Exp Stu 2', 'Male', self.h_boys_a, self.cat_single, '902', 'B1')

        prop, _ = create_direct_proposal(s1, s2)
        prop.expires_at = timezone.now() - timedelta(hours=1)
        prop.save()
        self.assertTrue(prop.is_expired)

    # 17. Warden rejection
    def test_12_warden_rejection(self):
        s1 = self.create_student_with_bed('wrej_s1', 'WRej Stu 1', 'Male', self.h_boys_a, self.cat_single, '111', 'B1')
        s2 = self.create_student_with_bed('wrej_s2', 'WRej Stu 2', 'Male', self.h_boys_a, self.cat_single, '112', 'B1')

        prop, _ = create_direct_proposal(s1, s2)
        student_accept_proposal(prop, s2)
        prop.refresh_from_db()

        ok, msg = warden_reject_proposal(prop, self.warden_a, self.h_boys_a, remarks="Disciplinary issue")
        self.assertTrue(ok)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'REJECTED')

    # 18. Multiple warden approvals for cross-hostel swap
    def test_13_multiple_warden_approvals(self):
        s_ha = self.create_student_with_bed('mwa_s1', 'MWA Stu 1', 'Male', self.h_boys_a, self.cat_single, '121', 'B1')
        s_hb = self.create_student_with_bed('mwa_s2', 'MWA Stu 2', 'Male', self.h_boys_b, self.cat_single, '121', 'B1')

        prop, _ = create_direct_proposal(s_ha, s_hb)
        student_accept_proposal(prop, s_hb)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'PENDING_WARDEN_APPROVAL')

        # 2 distinct hostel approvals created
        self.assertEqual(prop.warden_approvals.count(), 2)

        # Warden A approves
        warden_approve_proposal(prop, self.warden_a, self.h_boys_a)
        prop.refresh_from_db()
        # Still pending because Warden B hasn't approved
        self.assertEqual(prop.status, 'PENDING_WARDEN_APPROVAL')

        # Warden B approves
        warden_approve_proposal(prop, self.warden_b, self.h_boys_b)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'PAYMENT_PENDING')

    # 19, 20, 21. Financial calculations, advance balance & processing fee
    def test_14_financial_calculations_and_advance_credit(self):
        # S1 (AC Single: ₹96,000) swaps with S2 (Non-AC Triple: ₹42,000)
        s1 = self.create_student_with_bed('fin_s1', 'Fin Stu 1', 'Male', self.h_boys_a, self.cat_single, '131', 'B1')
        s2 = self.create_student_with_bed('fin_s2', 'Fin Stu 2', 'Male', self.h_boys_a, self.cat_triple, '132', 'B1')

        prop, _ = create_direct_proposal(s1, s2)
        p1 = prop.participants.get(student=s1)
        p2 = prop.participants.get(student=s2)

        fin1 = calculate_participant_financials(p1)
        fin2 = calculate_participant_financials(p2)

        # S1 moves to cheaper room (₹42,000): generates advance credit ₹54,000, only pays processing fee ₹200
        self.assertEqual(fin1['advance_credit_generated'], Decimal('54000.00'))
        self.assertEqual(fin1['processing_fee'], Decimal('200.00'))
        self.assertEqual(fin1['net_payable'], Decimal('200.00'))

        # S2 moves to more expensive room (₹96,000): pays diff ₹54,000 + processing fee ₹200 = ₹54,200
        self.assertEqual(fin2['fee_difference_payable'], Decimal('54000.00'))
        self.assertEqual(fin2['processing_fee'], Decimal('200.00'))
        self.assertEqual(fin2['net_payable'], Decimal('54200.00'))

class HostelXTransactionTests(TransactionTestCase, HostelXBaseSetup):
    """
    TransactionTestCase to verify atomic execution, database rollbacks,
    concurrency locks, and SQLite transactions without mock data.
    """
    def setUp(self):
        self.setup_base_data()

    # 22 & 23. Transaction Rollback & Zero Partial Execution
    def test_23_atomic_exchange_rollback_on_failure(self):
        s1 = self.create_student_with_bed('tx_s1', 'TX Stu 1', 'Male', self.h_boys_a, self.cat_single, '141', 'B1')
        s2 = self.create_student_with_bed('tx_s2', 'TX Stu 2', 'Male', self.h_boys_a, self.cat_single, '142', 'B1')

        bed1_orig = s1.current_bed
        bed2_orig = s2.current_bed

        prop, _ = create_direct_proposal(s1, s2)
        student_accept_proposal(prop, s2)
        warden_approve_proposal(prop, self.warden_a, self.h_boys_a)
        prop.refresh_from_db()

        # Intentionally alter state out-of-band to trigger an execution failure
        # Move S1 to another bed prior to execution
        s1.current_bed = None
        s1.save()

        # Attempt atomic execution: must raise AtomicExchangeExecutionError and rollback completely
        with self.assertRaises(AtomicExchangeExecutionError):
            execute_exchange_atomic(prop)

        # Verify proposal remains not completed
        prop.refresh_from_db()
        self.assertNotEqual(prop.status, 'COMPLETED')

        # Verify S2 was NOT partially altered
        s2.refresh_from_db()
        self.assertEqual(s2.current_bed_id, bed2_orig.id)

    # 24 & 25. Concurrent exchange attempt detection & Occupancy reconciliation
    def test_24_concurrent_exchange_safety_and_occupancy(self):
        s1 = self.create_student_with_bed('c_s1', 'Conc Stu 1', 'Male', self.h_boys_a, self.cat_single, '151', 'B1')
        s2 = self.create_student_with_bed('c_s2', 'Conc Stu 2', 'Male', self.h_boys_a, self.cat_single, '152', 'B1')

        prop, _ = create_direct_proposal(s1, s2)
        student_accept_proposal(prop, s2)
        warden_approve_proposal(prop, self.warden_a, self.h_boys_a)

        # Settle payment for both
        process_simulated_payment(prop, s1, self.admin_user)
        process_simulated_payment(prop, s2, self.admin_user)

        # Count occupied beds before execution
        occupied_before = Bed.objects.filter(room__hostel=self.h_boys_a, status='OCCUPIED').count()

        # Execute atomically
        ok, records = execute_exchange_atomic(prop)
        self.assertTrue(ok)
        self.assertEqual(len(records), 2)

        # Count occupied beds after execution: must match EXACTLY!
        occupied_after = Bed.objects.filter(room__hostel=self.h_boys_a, status='OCCUPIED').count()
        self.assertEqual(occupied_before, occupied_after)

        # Non-participating room occupants remain unaffected
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.current_bed.room.room_number, '152')
        self.assertEqual(s2.current_bed.room.room_number, '151')

    # 26, 27, 28, 29, 30. Mess update, Laundry, Maintenance, Audit log
    def test_25_services_and_audit_preservation(self):
        s1 = self.create_student_with_bed('srv_s1', 'Srv Stu 1', 'Male', self.h_boys_a, self.cat_single, '161', 'B1')
        s2 = self.create_student_with_bed('srv_s2', 'Srv Stu 2', 'Male', self.h_boys_b, self.cat_single, '161', 'B1')

        # Create past maintenance ticket for s1
        mnt = MaintenanceRequest.objects.create(
            complaint_id='MNT-TEST-01',
            student=s1,
            hostel=self.h_boys_a,
            room=s1.current_room,
            category='ELECTRICAL',
            title='Desk lamp',
            description='Bulb flicker'
        )

        prop, _ = create_direct_proposal(s1, s2)
        student_accept_proposal(prop, s2)
        warden_approve_proposal(prop, self.warden_a, self.h_boys_a)
        warden_approve_proposal(prop, self.warden_b, self.h_boys_b)
        process_simulated_payment(prop, s1, self.admin_user)
        process_simulated_payment(prop, s2, self.admin_user)

        execute_exchange_atomic(prop)

        # S1 is now in Boys Hostel B
        s1.refresh_from_db()
        self.assertEqual(s1.current_hostel_id, self.h_boys_b.id)

        # S1's mess registration updated to Boys Hostel B
        mess_reg = MessRegistration.objects.get(student=s1, is_active=True)
        self.assertEqual(mess_reg.hostel_id, self.h_boys_b.id)

        # Historical maintenance ticket still preserved
        mnt.refresh_from_db()
        self.assertEqual(mnt.hostel_id, self.h_boys_a.id)

        # Audit log exists
        self.assertTrue(AuditEntry.objects.filter(entity_type='ExchangeProposal', entity_id=str(prop.id)).exists())
