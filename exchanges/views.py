import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

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
