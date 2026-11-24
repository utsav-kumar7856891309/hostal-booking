from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q

from hostels.models import Hostel
from rooms.models import RoomCategory, Bed
from exchanges.models import ExchangeProposal, ExchangeRequest
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

    # 3. Exchange Proposal Status Breakdown
    status_choices_dict = dict(ExchangeProposal.STATUS_CHOICES)
    status_distribution = ExchangeProposal.objects.values('status').annotate(count=Count('id')).order_by('-count')
    status_labels = [status_choices_dict.get(s['status'], s['status']) for s in status_distribution]
    status_counts = [s['count'] for s in status_distribution]

    # 4. Exchange Requests Distribution by Preferred Hostel
    req_by_hostel = Hostel.objects.annotate(req_count=Count('preferred_in_requests')).filter(req_count__gt=0).order_by('-req_count')
    demand_labels = [h.name for h in req_by_hostel]
    demand_counts = [h.req_count for h in req_by_hostel]

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
        'status_labels': status_labels,
        'status_counts': status_counts,
        'demand_labels': demand_labels,
        'demand_counts': demand_counts,
        'total_processed_transfers': total_processed_transfers,
        'total_processing_fee_collected': total_processing_fee_collected,
    }
    return render(request, 'dashboards/dean_dashboard.html', context)
