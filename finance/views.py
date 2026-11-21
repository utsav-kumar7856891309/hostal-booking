from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from exchanges.models import ExchangeProposal, ProposalParticipant
from finance.models import StudentAccount, FinancialTransaction, TransferRecord
from finance.services import calculate_participant_financials, process_simulated_payment, check_proposal_financial_readiness
from finance.pdf import generate_transfer_letter_pdf
from exchanges.execution import execute_exchange_atomic, AtomicExchangeExecutionError

@login_required
def financial_settle_view(request, proposal_id):
    proposal = get_object_or_404(ExchangeProposal, id=proposal_id)
    user = request.user
    student = getattr(user, 'student_profile', None)

    participant = proposal.participants.filter(student=student).first() if student else None
    if not participant and not (user.is_admin_user or user.is_chief_warden):
        messages.error(request, "Access restricted to proposal participants.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    # If student is viewing, compute their specific financials
    if participant:
        my_fin = calculate_participant_financials(participant)
    else:
        # Admin viewing
        first_p = proposal.participants.first()
        my_fin = calculate_participant_financials(first_p) if first_p else None

    if request.method == 'POST' and 'simulate_payment' in request.POST:
        target_student = participant.student if participant else get_object_or_404(proposal.participants.all(), id=request.POST.get('participant_id')).student
        ok, msg = process_simulated_payment(proposal, target_student, user, test_gateway_ref="TEST-SIM")
        if ok:
            messages.success(request, msg)

            # Auto-check if all participants in cycle are settled!
            if check_proposal_financial_readiness(proposal) and proposal.status in ['APPROVED_BY_WARDENS', 'PAYMENT_PENDING']:
                try:
                    ok_exec, recs = execute_exchange_atomic(proposal, executed_by_user=user)
                    messages.success(request, "All participants settled! Exchange has been executed atomically.")
                    return redirect('proposal_detail', proposal_id=proposal.id)
                except AtomicExchangeExecutionError as ae:
                    messages.warning(request, f"Settlement recorded, but auto-execution paused: {ae}")
        else:
            messages.error(request, msg)

        return redirect('financial_settle', proposal_id=proposal.id)

    all_participants_fin = [
        {'p': p, 'fin': calculate_participant_financials(p)}
        for p in proposal.participants.all()
    ]

    context = {
        'proposal': proposal,
        'participant': participant,
        'my_fin': my_fin,
        'all_participants_fin': all_participants_fin,
    }
    return render(request, 'finance/settle.html', context)

@login_required
def my_financial_account(request):
    user = request.user
    student = getattr(user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students have financial accounts.")
        return redirect('dashboard_redirect')

    account, _ = StudentAccount.objects.get_or_create(student=student)
    transactions = student.transactions.order_by('-created_at')
    ledger_entries = account.ledger_entries.order_by('-timestamp')

    context = {
        'student': student,
        'account': account,
        'transactions': transactions,
        'ledger_entries': ledger_entries,
    }
    return render(request, 'finance/my_account.html', context)

@login_required
def download_transfer_letter_pdf(request, record_id):
    record = get_object_or_404(TransferRecord, id=record_id)
    # Check permission
    user = request.user
    if user.is_student and record.student.user_id != user.id:
        messages.error(request, "Permission denied.")
        return redirect('dashboard_redirect')

    pdf_bytes = generate_transfer_letter_pdf(record)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="HostelX_Transfer_{record.transfer_id}.pdf"'
    return response

@login_required
def view_transfer_letter_html(request, record_id):
    record = get_object_or_404(TransferRecord, id=record_id)
    user = request.user
    if user.is_student and record.student.user_id != user.id:
        messages.error(request, "Permission denied.")
        return redirect('dashboard_redirect')

    return render(request, 'finance/transfer_letter.html', {'record': record})
