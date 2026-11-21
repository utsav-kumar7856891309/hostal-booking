from decimal import Decimal
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from laundry.models import LaundryService, LaundryRequest

@login_required
def laundry_index(request):
    user = request.user
    student = getattr(user, 'student_profile', None)

    services = LaundryService.objects.filter(is_active=True)

    if student:
        requests = LaundryRequest.objects.filter(student=student).order_by('-created_at')
    else:
        # Wardens/Admin view all
        requests = LaundryRequest.objects.all().order_by('-created_at')[:50]

    if request.method == 'POST' and 'create_request' in request.POST:
        if not student:
            messages.error(request, "Only students can request laundry pickups.")
            return redirect('laundry_index')

        service_id = request.POST.get('service_id')
        item_count = Decimal(request.POST.get('item_count', '1.0'))
        special_instructions = request.POST.get('special_instructions', '')

        service = get_object_or_404(LaundryService, id=service_id)
        booking_code = f"LND-{timezone.now().strftime('%Y%m%d%H%M%S')}-{student.id}"

        pickup_time = timezone.now() + timedelta(hours=3)
        delivery_time = timezone.now() + timedelta(days=2)
        total_cost = service.rate_per_unit * item_count

        LaundryRequest.objects.create(
            booking_id=booking_code,
            student=student,
            hostel=student.current_hostel,
            service=service,
            item_count_or_weight=item_count,
            pickup_slot=pickup_time,
            delivery_slot=delivery_time,
            status='REQUESTED',
            special_instructions=special_instructions,
            total_cost=total_cost
        )
        messages.success(request, f"Laundry pickup requested! Booking Reference: {booking_code}")
        return redirect('laundry_index')

    context = {
        'services': services,
        'requests': requests,
        'student': student,
    }
    return render(request, 'laundry/index.html', context)
