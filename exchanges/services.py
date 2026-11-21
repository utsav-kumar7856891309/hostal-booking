import networkx as nx
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from exchanges.models import PolicyRule, ExchangeRequest, ExchangeProposal, ProposalParticipant
from approvals.models import WardenApproval
from students.models import Student
from notifications.models import Notification
from audit.models import AuditEntry

def validate_student_eligibility(student, policy=None):
    """
    Validates whether a student is eligible to propose or participate in an exchange.
    Returns (is_eligible: bool, reason: str).
    """
    if policy is None:
        policy = PolicyRule.get_current()

    if not policy.is_enabled:
        return False, "Hostel exchange program is currently disabled by university administration."

    if student.account_status != 'ACTIVE':
        return False, f"Account is {student.get_account_status_display().lower()}."

    if student.disciplinary_status == 'HOLD':
        return False, "Student has a disciplinary hold on record."

    if student.fee_status == 'UNPAID':
        return False, "Hostel fees are unpaid. Please clear dues before requesting an exchange."

    if not student.current_bed or not student.current_room or not student.current_hostel:
        return False, "No active bed allocation found for this student."

    # Check cooling-off period
    last_transfer = student.transfer_records.order_by('-transfer_date').first()
    if last_transfer:
        days_since = (timezone.now() - last_transfer.transfer_date).days
        if days_since < policy.cooling_off_days:
            return False, f"Cooling-off period active. Please wait {policy.cooling_off_days - days_since} more days before submitting a new exchange."

        # Check maximum exchanges per academic year
        current_year = timezone.now().year
        recent_transfers_count = student.transfer_records.filter(transfer_date__year=current_year).count()
        if recent_transfers_count >= policy.max_exchanges_per_year:
            return False, f"Maximum exchanges limit ({policy.max_exchanges_per_year} per year) reached for this academic year."

    # Check conflicting active pending proposals
    has_active_proposal = ProposalParticipant.objects.filter(
        student=student,
        proposal__status__in=['PROPOSED', 'ACCEPTED_BY_ALL', 'PENDING_WARDEN_APPROVAL', 'PAYMENT_PENDING']
    ).exists()
    if has_active_proposal:
        return False, "Student is already participating in an active exchange proposal."

    return True, "Eligible"

def does_student_accept_bed(request_obj, target_student):
    """
    Determines if target_student's current bed satisfies request_obj's criteria.
    """
    target_bed = target_student.current_bed
    if not target_bed:
        return False

    target_room = target_bed.room
    target_hostel = target_room.hostel

    # 1. Gender restriction: Strictly same gender
    if request_obj.student.gender != target_student.gender:
        return False

    # 2. Specific bed target
    if request_obj.specific_target_bed:
        return request_obj.specific_target_bed_id == target_bed.id

    # 3. Specific student target
    if request_obj.specific_target_student:
        return request_obj.specific_target_student_id == target_student.id

    # 4. Preferred Hostels
    preferred_hostel_ids = list(request_obj.preferred_hostels.values_list('id', flat=True))
    if preferred_hostel_ids and target_hostel.id not in preferred_hostel_ids:
        return False

    # 5. Preferred Categories
    preferred_cat_ids = list(request_obj.preferred_categories.values_list('id', flat=True))
    if preferred_cat_ids and target_room.category_id not in preferred_cat_ids:
        return False

    # 6. Preferred floor
    if request_obj.preferred_floor and target_room.floor != request_obj.preferred_floor:
        return False

    # 7. Don't swap with own bed
    if request_obj.current_bed_id == target_bed.id:
        return False

    return True

class ExchangeMatchingEngine:
    """
    Graph-based matching engine for finding 2-person to 5-person directed exchange cycles.
    """

    def __init__(self, policy=None):
        self.policy = policy or PolicyRule.get_current()

    def build_graph(self, active_requests=None):
        if active_requests is None:
            active_requests = ExchangeRequest.objects.filter(
                status='ACTIVE'
            ).select_related(
                'student', 'student__current_bed', 'student__current_room', 'student__current_hostel'
            ).prefetch_related('preferred_hostels', 'preferred_categories')

        G = nx.DiGraph()
        students_by_id = {}
        requests_by_student_id = {}

        # Add nodes
        for req in active_requests:
            stu = req.student
            # Validate eligibility
            is_ok, _ = validate_student_eligibility(stu, self.policy)
            if not is_ok:
                continue

            G.add_node(stu.id, student=stu, request=req)
            students_by_id[stu.id] = stu
            requests_by_student_id[stu.id] = req

        # Add directed edges: A -> B means A wants B's bed (A will move into B's bed)
        for u_id in G.nodes():
            u_req = requests_by_student_id[u_id]
            for v_id in G.nodes():
                if u_id == v_id:
                    continue
                v_stu = students_by_id[v_id]
                if does_student_accept_bed(u_req, v_stu):
                    G.add_edge(u_id, v_id)

        return G, students_by_id, requests_by_student_id

    def find_cycles(self, G, max_length=None):
        """
        Finds all elementary cycles of length between 2 and max_length (2 to 5).
        Returns a list of cycles, each cycle is a list of student_ids.
        """
        if max_length is None:
            max_length = self.policy.max_cycle_length

        all_cycles = []
        # Use bounded cycle detection to ensure fast execution
        # simple_cycles generates all simple cycles
        for cycle in nx.simple_cycles(G):
            if 2 <= len(cycle) <= max_length:
                all_cycles.append(cycle)

        # Sort cycles by length (direct 2-way first, then 3-way, etc.)
        all_cycles.sort(key=len)
        return all_cycles

    def generate_proposals_for_cycles(self, cycles, students_by_id, auto_commit=True):
        """
        Takes found cycles, filters non-conflicting ones, and creates ExchangeProposal objects.
        """
        created_proposals = []
        used_students = set()

        # Exclude students who already have an active pending proposal
        existing_pending_students = set(
            ProposalParticipant.objects.filter(
                proposal__status__in=['PROPOSED', 'ACCEPTED_BY_ALL', 'PENDING_WARDEN_APPROVAL', 'PAYMENT_PENDING']
            ).values_list('student_id', flat=True)
        )
        used_students.update(existing_pending_students)

        expiry_time = timezone.now() + timedelta(hours=self.policy.proposal_expiry_hours)

        for cycle in cycles:
            # Check if any student in this cycle is already part of another proposal
            if any(s_id in used_students for s_id in cycle):
                continue

            cycle_len = len(cycle)
            # Create proposal code
            timestamp_str = timezone.now().strftime('%Y%m%d%H%M%S')
            code = f"EXP-{timestamp_str}-{cycle[0]}"

            proposal = ExchangeProposal(
                proposal_code=code,
                cycle_length=cycle_len,
                status='PROPOSED',
                expires_at=expiry_time,
            )

            if auto_commit:
                proposal.save()

                participants = []
                # In cycle [S0, S1, S2]:
                # S0 moves to S1's bed
                # S1 moves to S2's bed
                # S2 moves to S0's bed
                for i in range(cycle_len):
                    curr_stu_id = cycle[i]
                    next_stu_id = cycle[(i + 1) % cycle_len]

                    curr_stu = students_by_id[curr_stu_id]
                    next_stu = students_by_id[next_stu_id]

                    part = ProposalParticipant.objects.create(
                        proposal=proposal,
                        student=curr_stu,
                        from_bed=curr_stu.current_bed,
                        to_bed=next_stu.current_bed,
                        status='PENDING'
                    )
                    participants.append(part)

                    # Mark requests as MATCHED
                    ExchangeRequest.objects.filter(student=curr_stu, status='ACTIVE').update(status='MATCHED')

                    # Notify student
                    Notification.objects.create(
                        recipient=curr_stu.user,
                        title="New Exchange Proposal Available!",
                        message=f"A {cycle_len}-party room exchange match has been found for you! Move to {next_stu.current_bed.full_code}. Please review and accept/decline.",
                        notification_type='PROPOSAL_NEW',
                        link=f"/exchanges/proposals/{proposal.id}/"
                    )

                created_proposals.append(proposal)

            # Mark all participants as used in this batch
            used_students.update(cycle)

        return created_proposals

def create_direct_proposal(student_a, student_b, remarks=""):
    """
    Directly creates a 2-student exchange proposal between Student A and Student B.
    Validates eligibility and mutual bed acceptance.
    """
    policy = PolicyRule.get_current()

    # 1. Validate both students
    ok_a, msg_a = validate_student_eligibility(student_a, policy)
    if not ok_a:
        return None, f"{student_a.full_name}: {msg_a}"

    ok_b, msg_b = validate_student_eligibility(student_b, policy)
    if not ok_b:
        return None, f"{student_b.full_name}: {msg_b}"

    # 2. Gender check
    if student_a.gender != student_b.gender:
        return None, "Exchanges are strictly permitted only between students of the same gender."

    # 3. Cross hostel policy check
    if student_a.current_hostel_id != student_b.current_hostel_id and not policy.allow_cross_hostel:
        return None, "Cross-hostel exchange is disabled by current university policy."

    # 4. Cross category policy check
    if student_a.current_room.category_id != student_b.current_room.category_id and not policy.allow_cross_category:
        return None, "Exchange between different room categories is disabled by current policy."

    # 5. Check if either student has an active pending proposal
    has_active_a = ProposalParticipant.objects.filter(
        student=student_a,
        proposal__status__in=['PROPOSED', 'ACCEPTED_BY_ALL', 'PENDING_WARDEN_APPROVAL', 'PAYMENT_PENDING']
    ).exists()
    if has_active_a:
        return None, f"{student_a.full_name} is already part of an active pending proposal."

    has_active_b = ProposalParticipant.objects.filter(
        student=student_b,
        proposal__status__in=['PROPOSED', 'ACCEPTED_BY_ALL', 'PENDING_WARDEN_APPROVAL', 'PAYMENT_PENDING']
    ).exists()
    if has_active_b:
        return None, f"{student_b.full_name} is already part of an active pending proposal."

    expiry_time = timezone.now() + timedelta(hours=policy.proposal_expiry_hours)
    code = f"DIR-{timezone.now().strftime('%Y%m%d%H%M%S')}-{student_a.id}-{student_b.id}"

    with transaction.atomic():
        proposal = ExchangeProposal.objects.create(
            proposal_code=code,
            cycle_length=2,
            status='PROPOSED',
            expires_at=expiry_time,
        )

        # Participant A: accepts right away since A initiated it!
        p_a = ProposalParticipant.objects.create(
            proposal=proposal,
            student=student_a,
            from_bed=student_a.current_bed,
            to_bed=student_b.current_bed,
            status='ACCEPTED',
            accepted_at=timezone.now(),
            remarks=remarks
        )

        # Participant B: pending acceptance
        p_b = ProposalParticipant.objects.create(
            proposal=proposal,
            student=student_b,
            from_bed=student_b.current_bed,
            to_bed=student_a.current_bed,
            status='PENDING',
        )

        # Notify student B
        Notification.objects.create(
            recipient=student_b.user,
            title="Direct Room Exchange Proposal Received",
            message=f"{student_a.full_name} has proposed an exchange with your bed ({student_b.current_bed.full_code}). Please review and respond.",
            notification_type='PROPOSAL_NEW',
            link=f"/exchanges/proposals/{proposal.id}/"
        )

        # Audit Entry
        AuditEntry.objects.create(
            actor=student_a.user,
            action='DIRECT_EXCHANGE_PROPOSED',
            entity_type='ExchangeProposal',
            entity_id=str(proposal.id),
            description=f"Direct proposal {proposal.proposal_code} created between {student_a.student_id} and {student_b.student_id}."
        )

    return proposal, "Proposal created successfully."

def student_accept_proposal(proposal, student, remarks=""):
    """
    Student accepts their participation in the proposal.
    If all participants accept:
      - Proposal advances to 'ACCEPTED_BY_ALL' / 'PENDING_WARDEN_APPROVAL'
      - WardenApproval records are automatically generated for each hostel involved!
    """
    if proposal.status != 'PROPOSED':
        return False, "This proposal is not currently awaiting student acceptances."

    if proposal.is_expired:
        proposal.status = 'EXPIRED'
        proposal.save()
        return False, "This proposal has expired."

    participant = proposal.participants.filter(student=student).first()
    if not participant:
        return False, "You are not a participant in this proposal."

    if participant.status == 'ACCEPTED':
        return True, "You have already accepted this proposal."

    with transaction.atomic():
        participant.status = 'ACCEPTED'
        participant.accepted_at = timezone.now()
        participant.remarks = remarks
        participant.save()

        # Check if all participants in the cycle have now accepted
        if proposal.all_participants_accepted:
            proposal.status = 'PENDING_WARDEN_APPROVAL'
            proposal.save()

            # Find all distinct hostels involved
            involved_hostel_ids = set()
            for p in proposal.participants.all():
                involved_hostel_ids.add(p.from_bed.room.hostel_id)
                involved_hostel_ids.add(p.to_bed.room.hostel_id)

            for h_id in involved_hostel_ids:
                WardenApproval.objects.get_or_create(
                    proposal=proposal,
                    hostel_id=h_id,
                    defaults={'status': 'PENDING'}
                )

            # Notify wardens of involved hostels
            for p in proposal.participants.all():
                wardens = p.from_bed.room.hostel.wardens.all()
                for w in wardens:
                    Notification.objects.create(
                        recipient=w.user,
                        title="New Room Exchange Approval Required",
                        message=f"Proposal {proposal.proposal_code} accepted by all students. Warden authorization required.",
                        notification_type='PROPOSAL_ACCEPTED',
                        link=f"/approvals/detail/{proposal.id}/"
                    )

            # Notify students
            for p in proposal.participants.all():
                Notification.objects.create(
                    recipient=p.student.user,
                    title="All Students Accepted Proposal!",
                    message=f"Proposal {proposal.proposal_code} accepted by all students. It has been routed to the hostel warden(s) for approval.",
                    notification_type='PROPOSAL_ACCEPTED',
                    link=f"/exchanges/proposals/{proposal.id}/"
                )

        AuditEntry.objects.create(
            actor=student.user,
            action='PROPOSAL_ACCEPTED_BY_STUDENT',
            entity_type='ExchangeProposal',
            entity_id=str(proposal.id),
            description=f"Student {student.student_id} accepted proposal {proposal.proposal_code}."
        )

    return True, "Proposal successfully accepted."

def student_decline_proposal(proposal, student, reason=""):
    """
    Student declines their participation in the proposal.
    The entire proposal is immediately marked REJECTED.
    No bed allocations change. Requests are released.
    """
    if proposal.status not in ['PROPOSED', 'ACCEPTED_BY_ALL']:
        return False, "This proposal cannot be declined at its current stage."

    participant = proposal.participants.filter(student=student).first()
    if not participant:
        return False, "You are not a participant in this proposal."

    with transaction.atomic():
        participant.status = 'DECLINED'
        participant.remarks = reason
        participant.save()

        proposal.status = 'REJECTED'
        proposal.rejection_reason = f"Declined by student {student.full_name} ({student.student_id}): {reason}"
        proposal.save()

        # Release requests back to ACTIVE
        for p in proposal.participants.all():
            ExchangeRequest.objects.filter(student=p.student, status='MATCHED').update(status='ACTIVE')

            if p.student != student:
                Notification.objects.create(
                    recipient=p.student.user,
                    title="Exchange Proposal Declined",
                    message=f"Proposal {proposal.proposal_code} was declined by a participant ({student.full_name}). Your request is back in the active pool.",
                    notification_type='PROPOSAL_DECLINED',
                    link=f"/exchanges/proposals/{proposal.id}/"
                )

        AuditEntry.objects.create(
            actor=student.user,
            action='PROPOSAL_DECLINED_BY_STUDENT',
            entity_type='ExchangeProposal',
            entity_id=str(proposal.id),
            description=f"Proposal {proposal.proposal_code} declined by {student.student_id}. Reason: {reason}"
        )

    return True, "Proposal declined and cancelled."
