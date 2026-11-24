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

        next_url = request.POST.get('next') or 'warden_approvals_queue'
        return redirect(next_url)

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

@login_required
def warden_approvals_queue(request):
    """
    Dedicated Approval Console for Wardens & Chief Warden.
    Shows pending proposals, multi-party participant chains, and historical approval audit trail.
    """
    user = request.user
    if not (user.is_warden or user.is_chief_warden or user.is_admin_user):
        messages.error(request, "Access restricted to hostel wardens.")
        return redirect('dashboard_redirect')

    warden = getattr(user, 'warden_profile', None)
    selected_hostel_code = request.GET.get('hostel')

    if selected_hostel_code:
        hostel = get_object_or_404(Hostel, code=selected_hostel_code)
    elif warden and warden.hostel:
        hostel = warden.hostel
    else:
        hostel = Hostel.objects.first()

    # If Chief Warden or Admin: can see all pending or filter by hostel
    if user.is_chief_warden or user.is_admin_user:
        base_approvals = WardenApproval.objects.all()
        if selected_hostel_code:
            base_approvals = base_approvals.filter(hostel=hostel)
    else:
        base_approvals = WardenApproval.objects.filter(hostel=hostel)

    pending_approvals = base_approvals.filter(
        status='PENDING',
        proposal__status__in=['PENDING_WARDEN_APPROVAL', 'ACCEPTED_BY_ALL']
    ).select_related('proposal', 'hostel').prefetch_related(
        'proposal__participants', 'proposal__participants__student',
        'proposal__participants__from_bed', 'proposal__participants__to_bed',
        'proposal__participants__from_bed__room', 'proposal__participants__to_bed__room'
    ).order_by('-proposal__created_at')

    # Approval History (Approved & Rejected)
    history_approvals = base_approvals.exclude(status='PENDING').select_related(
        'proposal', 'hostel', 'warden', 'warden__user'
    ).prefetch_related('proposal__participants').order_by('-decided_at')[:30]

    all_hostels = Hostel.objects.all()

    context = {
        'warden': warden,
        'hostel': hostel,
        'all_hostels': all_hostels,
        'pending_approvals': pending_approvals,
        'history_approvals': history_approvals,
        'pending_count': pending_approvals.count(),
        'history_count': history_approvals.count(),
    }
    return render(request, 'approvals/queue.html', context)
