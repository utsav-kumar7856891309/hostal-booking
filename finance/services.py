from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from exchanges.models import PolicyRule
from rooms.models import RoomPricing
from finance.models import StudentAccount, FinancialTransaction, FinancialLedgerEntry

def calculate_participant_financials(participant):
    """
    Calculates the financial breakdown for a student participating in an exchange:
    - Previous room annual fee
    - New room annual fee
    - Annual fee difference
    - Individual processing fee
    - Available advance balance
    - Advance balance used or generated
    - Net amount payable
    """
    policy = PolicyRule.get_current()
    student = participant.student
    from_bed = participant.from_bed
    to_bed = participant.to_bed

    # Look up pricing for previous room
    from_pricing = RoomPricing.objects.filter(
        hostel=from_bed.room.hostel,
        category=from_bed.room.category,
        is_active=True
    ).first()
    old_fee = from_pricing.annual_fee if from_pricing else Decimal('0.00')

    # Look up pricing for new room
    to_pricing = RoomPricing.objects.filter(
        hostel=to_bed.room.hostel,
        category=to_bed.room.category,
        is_active=True
    ).first()
    new_fee = to_pricing.annual_fee if to_pricing else Decimal('0.00')

    diff = new_fee - old_fee
    processing_fee = policy.processing_fee

    if diff > Decimal('0.00'):
        # New room is more expensive: student pays difference
        fee_difference_payable = diff
        advance_credit_generated = Decimal('0.00')
    else:
        # New room is cheaper: excess becomes advance credit for next year
        fee_difference_payable = Decimal('0.00')
        advance_credit_generated = abs(diff)

    account, _ = StudentAccount.objects.get_or_create(student=student)
    available_advance = account.balance

    # Calculate gross payable = difference + processing fee
    gross_payable = fee_difference_payable + processing_fee

    # Can use existing advance balance to offset payable
    advance_used = min(available_advance, gross_payable)
    net_payable = gross_payable - advance_used

    # Check if student already has a completed settlement transaction for this proposal
    existing_settlement = FinancialTransaction.objects.filter(
        proposal=participant.proposal,
        student=student,
        status='COMPLETED'
    ).exists()

    return {
        'student': student,
        'from_bed': from_bed,
        'to_bed': to_bed,
        'old_fee': old_fee,
        'new_fee': new_fee,
        'raw_difference': diff,
        'fee_difference_payable': fee_difference_payable,
        'advance_credit_generated': advance_credit_generated,
        'processing_fee': processing_fee,
        'available_advance': available_advance,
        'advance_used': advance_used,
        'net_payable': net_payable,
        'is_settled': existing_settlement or (net_payable == Decimal('0.00')),
    }

def process_simulated_payment(proposal, student, user, test_gateway_ref="SIM"):
    """
    Executes a simulated financial settlement for a student in a proposal.
    Explicitly tags the transaction as a simulated test transaction.
    Updates advance balance and records financial ledger entries.
    """
    fin = None
    for p in proposal.participants.all():
        if p.student_id == student.id:
            fin = calculate_participant_financials(p)
            break

    if not fin:
        return False, "Student is not a participant in this proposal."

    if fin['is_settled']:
        return True, "Financial settlement already completed for this participant."

    with transaction.atomic():
        account, _ = StudentAccount.objects.get_or_create(student=student)
        txn_ref = f"{test_gateway_ref}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{student.id}"

        # 1. Deduct advance balance if used
        if fin['advance_used'] > Decimal('0.00'):
            account.balance -= fin['advance_used']
            account.save()

        # 2. Add advance credit if moving to a cheaper room
        if fin['advance_credit_generated'] > Decimal('0.00'):
            account.balance += fin['advance_credit_generated']
            account.save()

        # 3. Create simulated payment transaction
        txn = FinancialTransaction.objects.create(
            student=student,
            proposal=proposal,
            transaction_type='SIMULATED_PAYMENT',
            amount=fin['net_payable'],
            status='COMPLETED',
            reference_id=txn_ref,
            is_simulated=True,
            notes=f"Simulated test settlement for Proposal {proposal.proposal_code}. "
                  f"Processing Fee: ₹{fin['processing_fee']}, Room Diff: ₹{fin['fee_difference_payable']}, "
                  f"Advance Used: ₹{fin['advance_used']}, Advance Credit: ₹{fin['advance_credit_generated']}."
        )

        # 4. Create Financial Ledger Entry
        FinancialLedgerEntry.objects.create(
            account=account,
            transaction=txn,
            entry_type='DEBIT' if fin['net_payable'] > 0 else 'CREDIT',
            amount=fin['net_payable'] if fin['net_payable'] > 0 else fin['advance_credit_generated'],
            balance_after=account.balance,
            description=f"Exchange settlement for Proposal {proposal.proposal_code} (Simulated)"
        )

    return True, f"Simulated payment of ₹{fin['net_payable']} completed successfully. Reference: {txn.reference_id}"

def check_proposal_financial_readiness(proposal):
    """
    Verifies if all participants in the proposal have satisfied their financial requirements.
    """
    for p in proposal.participants.all():
        fin = calculate_participant_financials(p)
        if not fin['is_settled']:
            return False
    return True
