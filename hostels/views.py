from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from decimal import Decimal

from hostels.models import Hostel, Warden, University
from rooms.models import Room, Bed, RoomCategory, RoomPricing
from students.models import Student
from approvals.models import WardenApproval
from exchanges.models import ExchangeProposal, PolicyRule
from maintenance.models import MaintenanceRequest
from laundry.models import LaundryRequest
from finance.models import StudentAccount, FinancialTransaction

@login_required
def warden_dashboard(request):
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

    # Bed Occupancy Metrics
    rooms = Room.objects.filter(hostel=hostel).select_related('category').prefetch_related('beds')
    beds = Bed.objects.filter(room__hostel=hostel)

    total_beds = beds.count()
    occupied_beds = beds.filter(status='OCCUPIED').count()
    vacant_beds = beds.filter(status='VACANT').count()
    blocked_beds = beds.filter(status='BLOCKED').count()
    maintenance_beds = beds.filter(status='MAINTENANCE').count()
    occupancy_pct = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0

    # Group rooms by floor for visual grid
    floors = {}
    for r in rooms:
        floors.setdefault(r.floor, []).append(r)

    # Pending Warden Approvals for this hostel
    pending_approvals = WardenApproval.objects.filter(
        hostel=hostel,
        status='PENDING',
        proposal__status__in=['PENDING_WARDEN_APPROVAL', 'ACCEPTED_BY_ALL']
    ).select_related('proposal').prefetch_related('proposal__participants')

    # Hostel resident students
    students = Student.objects.filter(current_hostel=hostel).select_related('current_room', 'current_bed', 'current_room__category')[:50]

    # Maintenance complaints in this hostel
    recent_maintenance = MaintenanceRequest.objects.filter(hostel=hostel).order_by('-created_at')[:10]

    # Laundry requests in this hostel
    recent_laundry = LaundryRequest.objects.filter(hostel=hostel).order_by('-created_at')[:10]

    all_hostels = Hostel.objects.all()

    context = {
        'warden': warden,
        'hostel': hostel,
        'all_hostels': all_hostels,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'vacant_beds': vacant_beds,
        'blocked_beds': blocked_beds,
        'maintenance_beds': maintenance_beds,
        'occupancy_pct': occupancy_pct,
        'floors': dict(sorted(floors.items())),
        'pending_approvals': pending_approvals,
        'students': students,
        'recent_maintenance': recent_maintenance,
        'recent_laundry': recent_laundry,
    }
    return render(request, 'dashboards/warden_dashboard.html', context)

@login_required
def chief_warden_dashboard(request):
    user = request.user
    if not (user.is_chief_warden or user.is_admin_user):
        messages.error(request, "Access restricted to the Chief Warden.")
        return redirect('dashboard_redirect')

    hostels = Hostel.objects.annotate(
        total_beds_cnt=Count('rooms__beds', distinct=True),
        occupied_beds_cnt=Count('rooms__beds', filter=Q(rooms__beds__status='OCCUPIED'), distinct=True),
        vacant_beds_cnt=Count('rooms__beds', filter=Q(rooms__beds__status='VACANT'), distinct=True),
    )

    all_active_proposals = ExchangeProposal.objects.filter(
        status__in=['PROPOSED', 'ACCEPTED_BY_ALL', 'PENDING_WARDEN_APPROVAL', 'PAYMENT_PENDING']
    ).prefetch_related('participants', 'warden_approvals')

    recent_completed_proposals = ExchangeProposal.objects.filter(status='COMPLETED').order_by('-completed_at')[:10]

    pending_warden_approvals = WardenApproval.objects.filter(status='PENDING').select_related('proposal', 'hostel')

    total_proposals = ExchangeProposal.objects.count()
    completed_proposals = ExchangeProposal.objects.filter(status='COMPLETED').count()

    context = {
        'hostels': hostels,
        'all_active_proposals': all_active_proposals,
        'recent_completed_proposals': recent_completed_proposals,
        'pending_warden_approvals': pending_warden_approvals,
        'total_proposals': total_proposals,
        'completed_proposals': completed_proposals,
    }
    return render(request, 'dashboards/chief_warden_dashboard.html', context)

@login_required
def admin_dashboard(request):
    user = request.user
    if not user.is_admin_user:
        messages.error(request, "Administrator privileges required.")
        return redirect('dashboard_redirect')

    hostels = Hostel.objects.all()
    categories = RoomCategory.objects.all()
    pricings = RoomPricing.objects.filter(is_active=True).select_related('hostel', 'category')
    policy = PolicyRule.get_current()

    total_students = Student.objects.count()
    total_hostels = Hostel.objects.count()
    total_rooms = Room.objects.count()
    total_beds = Bed.objects.count()
    occupied_beds = Bed.objects.filter(status='OCCUPIED').count()
    total_completed_exchanges = ExchangeProposal.objects.filter(status='COMPLETED').count()

    # Policy update handling
    if request.method == 'POST' and 'update_policy' in request.POST:
        policy.max_cycle_length = int(request.POST.get('max_cycle_length', 5))
        policy.allow_cross_hostel = 'allow_cross_hostel' in request.POST
        policy.allow_cross_category = 'allow_cross_category' in request.POST
        policy.allow_cross_academic_year = 'allow_cross_academic_year' in request.POST
        policy.allow_cross_course = 'allow_cross_course' in request.POST
        policy.processing_fee = Decimal(request.POST.get('processing_fee', '200.00'))
        policy.proposal_expiry_hours = int(request.POST.get('proposal_expiry_hours', 72))
        policy.cooling_off_days = int(request.POST.get('cooling_off_days', 30))
        policy.max_exchanges_per_year = int(request.POST.get('max_exchanges_per_year', 2))
        policy.save()
        messages.success(request, "Exchange policy rules updated successfully.")
        return redirect('admin_dashboard')

    context = {
        'hostels': hostels,
        'categories': categories,
        'pricings': pricings,
        'policy': policy,
        'total_students': total_students,
        'total_hostels': total_hostels,
        'total_rooms': total_rooms,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'total_completed_exchanges': total_completed_exchanges,
    }
    return render(request, 'dashboards/admin_dashboard.html', context)
