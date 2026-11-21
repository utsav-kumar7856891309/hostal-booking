from django.utils import timezone
from django.db import transaction

from approvals.models import WardenApproval
from audit.models import AuditEntry
from notifications.models import Notification
from exchanges.models import ExchangeRequest

def warden_approve_proposal(proposal, warden, hostel, remarks=""):
    """
    Hostel Warden approves the proposal for their assigned hostel.
    If all involved hostels have approved, the proposal advances to 'APPROVED_BY_WARDENS' / 'PAYMENT_PENDING'.
    """
    if proposal.status not in ['PENDING_WARDEN_APPROVAL', 'ACCEPTED_BY_ALL']:
        return False, "This proposal is not currently awaiting warden approvals."

    approval_rec = proposal.warden_approvals.filter(hostel=hostel).first()
    if not approval_rec:
        # If record didn't exist, create it (e.g. for chief warden or dynamic assignment)
        approval_rec = WardenApproval.objects.create(
            proposal=proposal,
            hostel=hostel,
            status='PENDING'
        )

    with transaction.atomic():
        approval_rec.status = 'APPROVED'
        approval_rec.warden = warden
        approval_rec.remarks = remarks
        approval_rec.decided_at = timezone.now()
        approval_rec.save()

        # Check if all required warden approvals for this proposal are now APPROVED
        if proposal.all_wardens_approved:
            proposal.status = 'PAYMENT_PENDING'
            proposal.save()

            # Notify all participating students to complete fee settlement
            for p in proposal.participants.all():
                Notification.objects.create(
                    recipient=p.student.user,
                    title="Exchange Approved by Wardens! Payment Pending",
                    message=f"All hostel wardens have approved proposal {proposal.proposal_code}. Please review fee difference & processing fee to finalize your room transfer.",
                    notification_type='WARDEN_DECISION',
                    link=f"/finance/settle/{proposal.id}/"
                )

        AuditEntry.objects.create(
            actor=warden.user if warden else None,
            action='WARDEN_APPROVAL_GRANTED',
            entity_type='ExchangeProposal',
            entity_id=str(proposal.id),
            description=f"Warden {warden} approved proposal {proposal.proposal_code} for {hostel.code}. Remarks: {remarks}"
        )

    return True, "Warden approval recorded successfully."

def warden_reject_proposal(proposal, warden, hostel, remarks=""):
    """
    Hostel Warden rejects the proposal.
    The entire proposal is marked REJECTED with remarks.
    All student requests are released back to ACTIVE.
    """
    if proposal.status not in ['PENDING_WARDEN_APPROVAL', 'ACCEPTED_BY_ALL']:
        return False, "This proposal is not currently awaiting warden review."

    approval_rec = proposal.warden_approvals.filter(hostel=hostel).first()
    if not approval_rec:
        approval_rec = WardenApproval.objects.create(
            proposal=proposal,
            hostel=hostel,
            status='PENDING'
        )

    with transaction.atomic():
        approval_rec.status = 'REJECTED'
        approval_rec.warden = warden
        approval_rec.remarks = remarks
        approval_rec.decided_at = timezone.now()
        approval_rec.save()

        proposal.status = 'REJECTED'
        proposal.rejection_reason = f"Rejected by Warden of {hostel.name} ({warden}): {remarks}"
        proposal.save()

        # Release requests back to ACTIVE
        for p in proposal.participants.all():
            ExchangeRequest.objects.filter(student=p.student, status='MATCHED').update(status='ACTIVE')

            Notification.objects.create(
                recipient=p.student.user,
                title="Exchange Proposal Rejected by Warden",
                message=f"Proposal {proposal.proposal_code} was rejected by {hostel.name} administration. Remarks: {remarks}",
                notification_type='WARDEN_DECISION',
                link=f"/exchanges/proposals/{proposal.id}/"
            )

        AuditEntry.objects.create(
            actor=warden.user if warden else None,
            action='WARDEN_APPROVAL_REJECTED',
            entity_type='ExchangeProposal',
            entity_id=str(proposal.id),
            description=f"Warden {warden} rejected proposal {proposal.proposal_code} for {hostel.code}. Reason: {remarks}"
        )

    return True, "Proposal successfully rejected."
