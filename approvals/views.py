from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from exchanges.models import ExchangeProposal
from approvals.models import WardenApproval
from approvals.services import warden_approve_proposal, warden_reject_proposal
from hostels.models import Hostel

@login_required
def approval_detail(request, proposal_id):
    proposal = get_object_or_404(ExchangeProposal, id=proposal_id)
    user = request.user
    if not (user.is_warden or user.is_chief_warden or user.is_admin_user):
        messages.error(request, "Permission denied.")
        return redirect('dashboard_redirect')

    warden = getattr(user, 'warden_profile', None)

    # Determine which hostel this warden can approve for
    if user.is_chief_warden or user.is_admin_user:
        # Chief warden or admin can approve for any pending hostel on this proposal
        pending_hostel_approval = proposal.warden_approvals.filter(status='PENDING').first()
        target_hostel = pending_hostel_approval.hostel if pending_hostel_approval else proposal.participants.first().from_bed.room.hostel
    elif warden and warden.hostel:
        target_hostel = warden.hostel
    else:
        target_hostel = None

    if request.method == 'POST':
        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '')
        hostel_id = request.POST.get('hostel_id')

        if hostel_id:
            target_hostel = get_object_or_404(Hostel, id=hostel_id)

        if not target_hostel:
            messages.error(request, "Target hostel for approval could not be determined.")
            return redirect('warden_dashboard')

        if action == 'approve':
            ok, msg = warden_approve_proposal(proposal, warden, target_hostel, remarks=remarks)
            if ok:
                messages.success(request, f"Approval granted for {target_hostel.name}.")
            else:
                messages.error(request, msg)
        elif action == 'reject':
            ok, msg = warden_reject_proposal(proposal, warden, target_hostel, remarks=remarks)
            if ok:
                messages.warning(request, f"Proposal rejected for {target_hostel.name}.")
            else:
                messages.error(request, msg)

        return redirect('warden_dashboard')

    participants = proposal.participants.select_related('student', 'from_bed', 'to_bed', 'from_bed__room', 'to_bed__room').all()
    warden_approvals = proposal.warden_approvals.select_related('hostel', 'warden').all()

    context = {
        'proposal': proposal,
        'participants': participants,
        'warden_approvals': warden_approvals,
        'target_hostel': target_hostel,
        'warden': warden,
    }
    return render(request, 'approvals/detail.html', context)
