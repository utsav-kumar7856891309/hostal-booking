import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from hostels.models import Hostel
from rooms.models import RoomCategory
from exchanges.models import ExchangeProposal, ProposalParticipant, ExchangeRequest, PolicyRule
from exchanges.services import (
    student_accept_proposal, student_decline_proposal,
    ExchangeMatchingEngine, validate_student_eligibility
)
from exchanges.execution import execute_exchange_atomic, AtomicExchangeExecutionError
from finance.services import calculate_participant_financials, check_proposal_financial_readiness

@login_required
def proposal_detail(request, proposal_id):
    proposal = get_object_or_404(ExchangeProposal, id=proposal_id)
    user = request.user
    student = getattr(user, 'student_profile', None)

    participants = list(proposal.participants.select_related(
        'student', 'from_bed', 'to_bed',
        'from_bed__room', 'to_bed__room',
        'from_bed__room__hostel', 'to_bed__room__hostel',
        'from_bed__room__category', 'to_bed__room__category'
    ).all())

    # Build sequence steps for cycle flow visualization
    # e.g. Step 1: S0 moves from Bed A to Bed B
    participant_financials = []
    for p in participants:
        fin = calculate_participant_financials(p)
        participant_financials.append({
            'participant': p,
            'fin': fin
        })

    # Find current user's participant record if student
    my_participant = None
    if student:
        for p in participants:
            if p.student_id == student.id:
                my_participant = p
                break

    # Wardens approvals
    warden_approvals = proposal.warden_approvals.select_related('hostel', 'warden').all()

    # Financial readiness
    is_financially_ready = check_proposal_financial_readiness(proposal)

    # Permission check for manual execution
    can_execute = (user.is_admin_user or user.is_chief_warden or user.is_warden) and (proposal.status in ['APPROVED_BY_WARDENS', 'PAYMENT_PENDING'])

    context = {
        'proposal': proposal,
        'participants': participants,
        'participant_financials': participant_financials,
        'my_participant': my_participant,
        'warden_approvals': warden_approvals,
        'is_financially_ready': is_financially_ready,
        'can_execute': can_execute,
    }
    return render(request, 'exchanges/proposal_detail.html', context)

@login_required
def accept_proposal(request, proposal_id):
    proposal = get_object_or_404(ExchangeProposal, id=proposal_id)
    student = getattr(request.user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students can accept proposals.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    remarks = request.POST.get('remarks', '')
    ok, msg = student_accept_proposal(proposal, student, remarks=remarks)
    if ok:
        messages.success(request, msg)
    else:
        messages.error(request, msg)

    return redirect('proposal_detail', proposal_id=proposal.id)

@login_required
def decline_proposal(request, proposal_id):
    proposal = get_object_or_404(ExchangeProposal, id=proposal_id)
    student = getattr(request.user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students can decline proposals.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    reason = request.POST.get('reason', 'Declined by student')
    ok, msg = student_decline_proposal(proposal, student, reason=reason)
    if ok:
        messages.warning(request, msg)
    else:
        messages.error(request, msg)

    return redirect('student_dashboard')

@login_required
def execute_proposal_now(request, proposal_id):
    proposal = get_object_or_404(ExchangeProposal, id=proposal_id)
    user = request.user
    if not (user.is_admin_user or user.is_chief_warden or user.is_warden):
        messages.error(request, "Permission denied.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    try:
        ok, records = execute_exchange_atomic(proposal, executed_by_user=user)
        messages.success(request, f"Exchange executed atomically! {len(records)} bed allocations updated successfully.")
    except AtomicExchangeExecutionError as err:
        messages.error(request, f"Execution failed: {err}")
    except Exception as e:
        messages.error(request, f"Unexpected error during execution: {e}")

    return redirect('proposal_detail', proposal_id=proposal.id)

@login_required
def find_matches(request):
    user = request.user
    if not (user.is_admin_user or user.is_chief_warden):
        messages.error(request, "Access restricted to administration.")
        return redirect('dashboard_redirect')

    policy = PolicyRule.get_current()
    engine = ExchangeMatchingEngine(policy=policy)

    start_time = time.time()
    G, students_by_id, requests_by_student_id = engine.build_graph()
    cycles = engine.find_cycles(G, max_length=policy.max_cycle_length)
    elapsed_time = round((time.time() - start_time) * 1000, 2)  # milliseconds

    # Group cycles by length (2, 3, 4, 5)
    cycles_by_len = {2: [], 3: [], 4: [], 5: []}
    for c in cycles:
        if len(c) in cycles_by_len:
            cycles_by_len[len(c)].append([students_by_id[s_id] for s_id in c])

    if request.method == 'POST' and 'generate_proposals' in request.POST:
        proposals = engine.generate_proposals_for_cycles(cycles, students_by_id, auto_commit=True)
        messages.success(request, f"Generated {len(proposals)} new exchange proposals across eligible cycles!")
        return redirect('chief_warden_dashboard')

    context = {
        'total_nodes': G.number_of_nodes(),
        'total_edges': G.number_of_edges(),
        'total_cycles': len(cycles),
        'elapsed_time_ms': elapsed_time,
        'cycles_by_len': cycles_by_len,
        'policy': policy,
    }
    return render(request, 'exchanges/find_matches.html', context)

@login_required
def available_exchange_requests(request):
    """
    Live Open Request Pool:
    Allows students and staff to view active room exchange requests across eligible hostels,
    filter by hostel / category, and propose direct 1-to-1 swaps with matching peers.
    """
    user = request.user
    student = getattr(user, 'student_profile', None)

    # Base queryset: only ACTIVE exchange requests
    requests_qs = ExchangeRequest.objects.filter(status='ACTIVE').select_related(
        'student', 'student__user', 'current_bed', 'current_bed__room',
        'current_bed__room__hostel', 'current_bed__room__category'
    ).prefetch_related('preferred_hostels', 'preferred_categories').order_by('-created_at')

    # Gender block rule (P04 policy): male students can only swap with male students, female with female
    if student and student.gender:
        requests_qs = requests_qs.filter(student__gender=student.gender)

    # Filter parameters
    hostel_id = request.GET.get('hostel')
    category_id = request.GET.get('category')
    search_q = request.GET.get('q', '').strip()
    match_my_bed = request.GET.get('match_my_bed') == '1'

    if hostel_id and hostel_id.isdigit():
        requests_qs = requests_qs.filter(current_bed__room__hostel_id=int(hostel_id))

    if category_id and category_id.isdigit():
        requests_qs = requests_qs.filter(current_bed__room__category_id=int(category_id))

    if search_q:
        requests_qs = requests_qs.filter(
            Q(student__registration_number__icontains=search_q) |
            Q(student__full_name__icontains=search_q) |
            Q(reason__icontains=search_q) |
            Q(current_bed__bed_identifier__icontains=search_q) |
            Q(current_bed__room__room_number__icontains=search_q) |
            Q(current_bed__room__hostel__name__icontains=search_q)
        )

    # Filter: requester's preferences accept student's current bed
    if match_my_bed and student and student.current_bed and student.current_room:
        my_hostel = student.current_hostel
        my_category = student.current_room.category
        requests_qs = requests_qs.filter(
            Q(preferred_hostels=my_hostel) | Q(preferred_hostels__isnull=True)
        ).filter(
            Q(preferred_categories=my_category) | Q(preferred_categories__isnull=True)
        ).distinct()

    # Hostels & Categories for dropdown filters
    hostels = Hostel.objects.all()
    if student and student.gender:
        hostels = hostels.filter(gender=student.gender)
    categories = RoomCategory.objects.all()

    total_count = requests_qs.count()

    context = {
        'student': student,
        'exchange_requests': requests_qs,
        'hostels': hostels,
        'categories': categories,
        'selected_hostel': int(hostel_id) if hostel_id and hostel_id.isdigit() else None,
        'selected_category': int(category_id) if category_id and category_id.isdigit() else None,
        'search_q': search_q,
        'match_my_bed': match_my_bed,
        'total_count': total_count,
    }
    return render(request, 'exchanges/available_requests.html', context)
