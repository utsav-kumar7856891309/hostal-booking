from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q

from hostels.models import Hostel
from rooms.models import RoomCategory, Bed
from exchanges.models import ExchangeProposal
from mess.models import ServiceFeedback
from maintenance.models import MaintenanceRequest
from finance.models import FinancialTransaction, TransferRecord
from audit.models import AuditEntry

@login_required
def dean_dashboard(request):
    user = request.user
    if not (user.is_dean or user.is_admin_user or user.is_chief_warden):
        messages.error(request, "Access restricted to Dean / Executive management.")
        return redirect('dashboard_redirect')

    # 1. Occupancy Data per Hostel for Chart.js
    hostels = Hostel.objects.annotate(
        total_beds=Count('rooms__beds', distinct=True),
        occupied_beds=Count('rooms__beds', filter=Q(rooms__beds__status='OCCUPIED'), distinct=True),
        vacant_beds=Count('rooms__beds', filter=Q(rooms__beds__status='VACANT'), distinct=True),
    )

    hostel_labels = [h.name for h in hostels]
    hostel_occupied = [h.occupied_beds for h in hostels]
    hostel_vacant = [h.vacant_beds for h in hostels]

    # 2. Cycle Length Distribution (2, 3, 4, 5 students)
    cycle_distribution = ExchangeProposal.objects.values('cycle_length').annotate(count=Count('id')).order_by('cycle_length')
    cycle_labels = [f"{cd['cycle_length']}-Party Cycle" for cd in cycle_distribution]
    cycle_counts = [cd['count'] for cd in cycle_distribution]

    # 3. Maintenance Requests by Category
    maint_by_cat = MaintenanceRequest.objects.values('category').annotate(count=Count('id')).order_by('-count')
    maint_labels = [dict(MaintenanceRequest.CATEGORY_CHOICES).get(m['category'], m['category']) for m in maint_by_cat]
    maint_counts = [m['count'] for m in maint_by_cat]

    # 4. Mess Ratings Distribution
    mess_ratings = ServiceFeedback.objects.filter(service_type='MESS').values('rating').annotate(count=Count('id')).order_by('rating')
    rating_labels = [f"{r['rating']} Stars" for r in mess_ratings]
    rating_counts = [r['count'] for r in mess_ratings]

    # 5. Financial aggregates
    total_processed_transfers = TransferRecord.objects.count()
    total_processing_fee_collected = FinancialTransaction.objects.filter(
        transaction_type='SIMULATED_PAYMENT',
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'hostels': hostels,
        'hostel_labels': hostel_labels,
        'hostel_occupied': hostel_occupied,
        'hostel_vacant': hostel_vacant,
        'cycle_labels': cycle_labels,
        'cycle_counts': cycle_counts,
        'maint_labels': maint_labels,
        'maint_counts': maint_counts,
        'rating_labels': rating_labels,
        'rating_counts': rating_counts,
        'total_processed_transfers': total_processed_transfers,
        'total_processing_fee_collected': total_processing_fee_collected,
    }
    return render(request, 'dashboards/dean_dashboard.html', context)

@login_required
def reports_index(request):
    transfer_records = TransferRecord.objects.select_related(
        'student', 'previous_hostel', 'previous_room', 'previous_bed',
        'new_hostel', 'new_room', 'new_bed'
    ).order_by('-transfer_date')[:50]

    recent_audits = AuditEntry.objects.select_related('actor').order_by('-timestamp')[:50]

    context = {
        'transfer_records': transfer_records,
        'recent_audits': recent_audits,
    }
    return render(request, 'reports/index.html', context)
