from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from rooms.models import Bed, Room, RoomCategory, RoomPricing
from hostels.models import Hostel
from students.models import Student
from allocations.models import BedAllocation, RoomBooking
from finance.models import StudentAccount, FinancialTransaction, FinancialLedgerEntry
from audit.models import AuditEntry
from notifications.models import Notification

@login_required
def room_booking_catalog(request):
    """
    Catalog of vacant beds across campus available for direct booking.
    """
    user = request.user
    student = getattr(user, 'student_profile', None)

    # Base query for vacant beds
    vacant_beds = Bed.objects.filter(status='VACANT').select_related(
        'room', 'room__hostel', 'room__category'
    )

    # Filter by gender if student is logged in
    if student:
        vacant_beds = vacant_beds.filter(room__hostel__gender=student.gender)

    # Filter parameters
    selected_hostel = request.GET.get('hostel')
    selected_cat = request.GET.get('category')
    selected_floor = request.GET.get('floor')
    selected_ac = request.GET.get('is_ac')

    if selected_hostel:
        vacant_beds = vacant_beds.filter(room__hostel__code=selected_hostel)
    if selected_cat:
        vacant_beds = vacant_beds.filter(room__category_id=selected_cat)
    if selected_floor:
        vacant_beds = vacant_beds.filter(room__floor=selected_floor)
    if selected_ac in ['0', '1']:
        vacant_beds = vacant_beds.filter(room__category__is_ac=(selected_ac == '1'))

    # Attach annual fee to each bed
    pricing_dict = {}
    for p in RoomPricing.objects.filter(is_active=True):
        pricing_dict[(p.hostel_id, p.category_id)] = p.annual_fee

    bed_items = []
    for bed in vacant_beds[:120]:
        price = pricing_dict.get((bed.room.hostel_id, bed.room.category_id), Decimal('50000.00'))
        bed_items.append({
            'bed': bed,
            'price': price,
        })

    all_hostels = Hostel.objects.filter(gender=student.gender) if student else Hostel.objects.all()
    all_categories = RoomCategory.objects.all()

    context = {
        'student': student,
        'bed_items': bed_items,
        'total_vacant': len(bed_items),
        'hostels': all_hostels,
        'categories': all_categories,
        'selected_hostel': selected_hostel,
        'selected_cat': selected_cat,
        'selected_floor': selected_floor,
        'selected_ac': selected_ac,
    }
    return render(request, 'allocations/booking_catalog.html', context)

@login_required
def room_booking_detail(request, bed_id):
    """
    Review details and fee calculation before confirming direct booking.
    """
    user = request.user
    student = getattr(user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students can book hostel beds.")
        return redirect('dashboard_redirect')

    if student.student_type == 'DAY_SCHOLAR':
        messages.warning(request, "Day Scholar is not eligible for hostel room booking.")
        return redirect('student_dashboard')

    bed = get_object_or_404(Bed.objects.select_related('room', 'room__hostel', 'room__category'), id=bed_id)

    if bed.status != 'VACANT':
        messages.error(request, "Sorry, this bed is no longer vacant.")
        return redirect('room_booking_catalog')

    if bed.room.hostel.gender != student.gender:
        messages.error(request, f"Gender restriction: You can only book beds in {student.gender} hostels.")
        return redirect('room_booking_catalog')

    pricing = RoomPricing.objects.filter(
        hostel=bed.room.hostel,
        category=bed.room.category,
        is_active=True
    ).first()
    annual_fee = pricing.annual_fee if pricing else Decimal('60000.00')

    account, _ = StudentAccount.objects.get_or_create(student=student)
    available_advance = account.balance
    advance_used = min(available_advance, annual_fee)
    net_payable = annual_fee - advance_used

    context = {
        'student': student,
        'bed': bed,
        'annual_fee': annual_fee,
        'account': account,
        'advance_used': advance_used,
        'net_payable': net_payable,
    }
    return render(request, 'allocations/booking_detail.html', context)

@login_required
def room_booking_confirm(request, bed_id):
    """
    POST handler: Atomically confirms direct room booking, allotting the bed,
    creating accounting entries, and issuing an allotment certificate.
    """
    if request.method != 'POST':
        return redirect('room_booking_detail', bed_id=bed_id)

    user = request.user
    student = getattr(user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students can book rooms.")
        return redirect('dashboard_redirect')

    if student.student_type == 'DAY_SCHOLAR':
        messages.warning(request, "Day Scholar is not eligible for hostel room booking.")
        return redirect('student_dashboard')

    if student.account_status != 'ACTIVE':
        messages.error(request, f"Your account status is {student.get_account_status_display()}. Booking is not allowed.")
        return redirect('student_dashboard')

    if student.disciplinary_status == 'HOLD':
        messages.error(request, "You have a disciplinary hold on record. Room booking is blocked.")
        return redirect('student_dashboard')

    now = timezone.now()

    try:
        with transaction.atomic():
            # Lock the bed record with select_for_update
            bed = Bed.objects.select_for_update().get(id=bed_id)

            if bed.status != 'VACANT':
                messages.error(request, "This bed has just been allocated to another student. Please select another vacant bed.")
                return redirect('room_booking_catalog')

            pricing = RoomPricing.objects.filter(
                hostel=bed.room.hostel,
                category=bed.room.category,
                is_active=True
            ).first()
            annual_fee = pricing.annual_fee if pricing else Decimal('60000.00')

            account, _ = StudentAccount.objects.get_or_create(student=student)
            advance_used = min(account.balance, annual_fee)
            net_payable = annual_fee - advance_used

            # If student already had an active bed allocation, deactivate and vacate old bed
            if student.current_bed:
                old_bed = student.current_bed
                old_bed.status = 'VACANT'
                old_bed.save(update_fields=['status'])

                BedAllocation.objects.filter(
                    student=student,
                    bed=old_bed,
                    is_active=True
                ).update(
                    is_active=False,
                    end_date=now,
                    remarks=f"Vacated due to Direct Booking {bed.full_code}"
                )

            # 1. Update Bed status to OCCUPIED
            bed.status = 'OCCUPIED'
            bed.save(update_fields=['status'])

            # 2. Create new active BedAllocation
            allocation = BedAllocation.objects.create(
                student=student,
                bed=bed,
                academic_year='2026-2027',
                start_date=now,
                is_active=True,
                remarks='Direct Online Room Booking Allotment'
            )

            # 3. Update Student current location & residency
            student.current_hostel = bed.room.hostel
            student.current_room = bed.room
            student.current_bed = bed
            student.student_type = 'HOSTEL'
            student.fee_status = 'PAID'
            student.save(update_fields=['current_hostel', 'current_room', 'current_bed', 'student_type', 'fee_status'])

            # 4. Update financial account & create transaction
            if advance_used > 0:
                account.balance -= advance_used
                account.save(update_fields=['balance'])

            bkg_code = f"BKG-{now.strftime('%Y%m%d%H%M')}-{student.id}"
            txn_ref = f"TXN-BKG-{now.strftime('%Y%m%d%H%M%S')}-{student.id}"

            txn = FinancialTransaction.objects.create(
                student=student,
                transaction_type='ANNUAL_FEE_PAYMENT',
                amount=net_payable,
                status='COMPLETED',
                reference_id=txn_ref,
                is_simulated=True,
                notes=f"Direct Room Booking fee payment for {bed.full_code} ({bed.room.category.name}). Advance used: ₹{advance_used}."
            )

            FinancialLedgerEntry.objects.create(
                account=account,
                transaction=txn,
                entry_type='DEBIT',
                amount=net_payable,
                balance_after=account.balance,
                description=f"Direct Room Booking fee payment for {bed.full_code}"
            )

            # 5. Create RoomBooking record
            booking = RoomBooking.objects.create(
                booking_id=bkg_code,
                student=student,
                bed=bed,
                academic_year='2026-2027',
                annual_fee=annual_fee,
                amount_paid=net_payable,
                status='CONFIRMED',
                booking_date=now,
                remarks=f"Direct booking confirmed. Allotted bed {bed.full_code}.",
                transaction=txn
            )

            # 6. Audit log & Notification
            AuditEntry.objects.create(
                actor=user,
                action='DIRECT_ROOM_BOOKED',
                entity_type='RoomBooking',
                entity_id=str(booking.id),
                description=f"Direct room booking confirmed: Student {student.student_id} allocated bed {bed.full_code}."
            )

            Notification.objects.create(
                recipient=user,
                title="Hostel Room Booking Confirmed!",
                message=f"Congratulations! Bed {bed.full_code} in {bed.room.hostel.name} has been successfully allotted to you. Booking Ref: {booking.booking_id}.",
                notification_type='SERVICE_UPDATE',
                link=f"/bookings/{booking.id}/"
            )

            messages.success(request, f"Room booking confirmed! Bed {bed.full_code} has been allotted to you.")
            return redirect('booking_receipt', booking_id=booking.id)

    except Exception as e:
        messages.error(request, f"Booking transaction failed: {str(e)}")
        return redirect('room_booking_catalog')

@login_required
def booking_receipt(request, booking_id):
    """
    Printable booking allotment certificate and receipt.
    """
    booking = get_object_or_404(RoomBooking, id=booking_id)
    user = request.user

    # Permission check: student owner or staff
    if user.is_student and booking.student.user_id != user.id:
        messages.error(request, "Permission denied.")
        return redirect('dashboard_redirect')

    context = {
        'booking': booking,
        'student': booking.student,
        'bed': booking.bed,
        'room': booking.bed.room,
        'hostel': booking.bed.room.hostel,
    }
    return render(request, 'allocations/booking_receipt.html', context)

@login_required
def my_bookings_list(request):
    """
    List of direct bookings for logged in student.
    """
    user = request.user
    student = getattr(user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students have room booking records.")
        return redirect('dashboard_redirect')

    bookings = student.direct_bookings.all().order_by('-booking_date')
    return render(request, 'allocations/my_bookings.html', {'bookings': bookings, 'student': student})
