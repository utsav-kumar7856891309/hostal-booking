from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from hostels.models import Hostel, University
from rooms.models import Room, Bed, RoomCategory, RoomPricing
from students.models import Student
from allocations.models import BedAllocation, RoomBooking
from exchanges.models import PolicyRule, ExchangeProposal
from finance.models import StudentAccount, FinancialTransaction, FinancialLedgerEntry
from audit.models import AuditEntry
from notifications.models import Notification

def verify_admin(user):
    return user.is_authenticated and (user.is_admin_user or user.is_superuser)

@login_required
def admin_panel_overview(request):
    """
    Main Administration Control Center
    """
    if not verify_admin(request.user):
        messages.error(request, "Administrator privileges required to access Admin Control Panel.")
        return redirect('dashboard_redirect')

    hostels = Hostel.objects.all()
    categories = RoomCategory.objects.all()
    total_students = Student.objects.count()
    total_rooms = Room.objects.count()
    total_beds = Bed.objects.count()
    occupied_beds = Bed.objects.filter(status='OCCUPIED').count()
    vacant_beds = Bed.objects.filter(status='VACANT').count()
    total_bookings = RoomBooking.objects.count()
    total_exchanges = ExchangeProposal.objects.filter(status='COMPLETED').count()

    recent_bookings = RoomBooking.objects.select_related('student', 'bed', 'bed__room', 'bed__room__hostel').order_by('-booking_date')[:8]
    recent_audits = AuditEntry.objects.select_related('actor').order_by('-timestamp')[:8]

    context = {
        'hostels': hostels,
        'categories': categories,
        'total_students': total_students,
        'total_rooms': total_rooms,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'vacant_beds': vacant_beds,
        'total_bookings': total_bookings,
        'total_exchanges': total_exchanges,
        'recent_bookings': recent_bookings,
        'recent_audits': recent_audits,
    }
    return render(request, 'admin_panel/overview.html', context)

@login_required
def admin_rooms_manager(request):
    """
    Manage rooms and individual beds with live status changer.
    """
    if not verify_admin(request.user):
        messages.error(request, "Admin access required.")
        return redirect('dashboard_redirect')

    hostel_code = request.GET.get('hostel')
    category_id = request.GET.get('category')
    search_q = request.GET.get('q', '').strip()

    rooms = Room.objects.select_related('hostel', 'category').prefetch_related('beds').all()
    if hostel_code:
        rooms = rooms.filter(hostel__code=hostel_code)
    if category_id:
        rooms = rooms.filter(category_id=category_id)
    if search_q:
        rooms = rooms.filter(room_number__icontains=search_q)

    hostels = Hostel.objects.all()
    categories = RoomCategory.objects.all()

    context = {
        'rooms': rooms[:100],
        'total_rooms_found': rooms.count(),
        'hostels': hostels,
        'categories': categories,
        'selected_hostel': hostel_code,
        'selected_cat': category_id,
        'search_q': search_q,
    }
    return render(request, 'admin_panel/rooms_manager.html', context)

@login_required
def admin_add_room(request):
    """
    Admin adds a new room and automatically generates its beds.
    """
    if not verify_admin(request.user):
        messages.error(request, "Admin access required.")
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        hostel_id = request.POST.get('hostel_id')
        room_number = request.POST.get('room_number', '').strip()
        floor = request.POST.get('floor', 1)
        category_id = request.POST.get('category_id')

        hostel = get_object_or_404(Hostel, id=hostel_id)
        category = get_object_or_404(RoomCategory, id=category_id)

        if Room.objects.filter(hostel=hostel, room_number=room_number).exists():
            messages.error(request, f"Room {room_number} already exists in {hostel.name}.")
            return redirect('admin_rooms_manager')

        with transaction.atomic():
            room = Room.objects.create(
                hostel=hostel,
                room_number=room_number,
                floor=int(floor),
                category=category,
                is_active=True
            )
            # Create beds based on category capacity
            for i in range(1, category.capacity + 1):
                Bed.objects.create(
                    room=room,
                    bed_identifier=f"B{i}",
                    status='VACANT'
                )

            AuditEntry.objects.create(
                actor=request.user,
                action='ADMIN_ROOM_CREATED',
                entity_type='Room',
                entity_id=str(room.id),
                description=f"Admin created room {room.room_number} with {category.capacity} beds in {hostel.code}."
            )

        messages.success(request, f"Room {room.room_number} with {category.capacity} vacant beds created in {hostel.name}!")
        return redirect('admin_rooms_manager')

    return redirect('admin_rooms_manager')

@login_required
def admin_update_bed_status(request, bed_id):
    """
    Admin quickly changes bed status (VACANT, OCCUPIED, BLOCKED, MAINTENANCE).
    """
    if not verify_admin(request.user):
        messages.error(request, "Admin access required.")
        return redirect('dashboard_redirect')

    bed = get_object_or_404(Bed, id=bed_id)
    new_status = request.POST.get('status')

    if new_status in ['VACANT', 'OCCUPIED', 'BLOCKED', 'MAINTENANCE']:
        old_status = bed.status
        bed.status = new_status
        bed.save(update_fields=['status'])

        # If marking vacant, deactivate any active allocation
        if new_status == 'VACANT':
            BedAllocation.objects.filter(bed=bed, is_active=True).update(
                is_active=False,
                end_date=timezone.now(),
                remarks="Deactivated by Admin bed status change"
            )
            Student.objects.filter(current_bed=bed).update(current_bed=None, current_room=None, current_hostel=None)

        AuditEntry.objects.create(
            actor=request.user,
            action='ADMIN_BED_STATUS_UPDATE',
            entity_type='Bed',
            entity_id=str(bed.id),
            description=f"Admin changed bed {bed.full_code} status from {old_status} to {new_status}."
        )
        messages.success(request, f"Bed {bed.full_code} status updated to {new_status}.")

    return redirect('admin_rooms_manager')

@login_required
def admin_bookings_manager(request):
    """
    Admin views all direct room bookings and has a manual allotment tool.
    """
    if not verify_admin(request.user):
        messages.error(request, "Admin access required.")
        return redirect('dashboard_redirect')

    bookings = RoomBooking.objects.select_related('student', 'bed', 'bed__room', 'bed__room__hostel').order_by('-booking_date')

    # Students without a bed for manual allotment
    unallocated_students = Student.objects.filter(current_bed__isnull=True, account_status='ACTIVE')
    vacant_beds = Bed.objects.filter(status='VACANT').select_related('room', 'room__hostel')

    context = {
        'bookings': bookings,
        'unallocated_students': unallocated_students,
        'vacant_beds': vacant_beds,
    }
    return render(request, 'admin_panel/bookings_manager.html', context)

@login_required
def admin_manual_allot(request):
    """
    Admin manually allots any student directly to any vacant bed.
    """
    if not verify_admin(request.user):
        messages.error(request, "Admin access required.")
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        bed_id = request.POST.get('bed_id')

        student = get_object_or_404(Student, id=student_id)
        bed = get_object_or_404(Bed, id=bed_id)

        if bed.status != 'VACANT':
            messages.error(request, "Selected bed is not vacant.")
            return redirect('admin_bookings_manager')

        now = timezone.now()
        with transaction.atomic():
            # Release old bed if any
            if student.current_bed:
                old_bed = student.current_bed
                old_bed.status = 'VACANT'
                old_bed.save()
                BedAllocation.objects.filter(student=student, bed=old_bed, is_active=True).update(
                    is_active=False,
                    end_date=now
                )

            bed.status = 'OCCUPIED'
            bed.save(update_fields=['status'])

            BedAllocation.objects.create(
                student=student,
                bed=bed,
                academic_year='2026-2027',
                start_date=now,
                is_active=True,
                remarks='Direct Admin Manual Allotment'
            )

            student.current_hostel = bed.room.hostel
            student.current_room = bed.room
            student.current_bed = bed
            student.student_type = 'HOSTEL'
            student.save(update_fields=['current_hostel', 'current_room', 'current_bed', 'student_type'])

            bkg_code = f"ADM-ALLOT-{now.strftime('%Y%m%d%H%M')}-{student.id}"
            RoomBooking.objects.create(
                booking_id=bkg_code,
                student=student,
                bed=bed,
                academic_year='2026-2027',
                annual_fee=Decimal('0.00'),
                amount_paid=Decimal('0.00'),
                status='CONFIRMED',
                remarks='Direct Administrative Allotment'
            )

            AuditEntry.objects.create(
                actor=request.user,
                action='ADMIN_MANUAL_ALLOTMENT',
                entity_type='Student',
                entity_id=str(student.id),
                description=f"Admin manually allotted bed {bed.full_code} to student {student.student_id}."
            )

            Notification.objects.create(
                recipient=student.user,
                title="Direct Room Allotment by University Administration",
                message=f"You have been directly allotted bed {bed.full_code} in {bed.room.hostel.name} by the administration.",
                notification_type='SERVICE_UPDATE'
            )

            messages.success(request, f"Bed {bed.full_code} successfully allotted to {student.full_name} ({student.student_id})!")

    return redirect('admin_bookings_manager')

@login_required
def admin_students_manager(request):
    """
    Searchable Central University Student Database directory with status toggles.
    """
    if not verify_admin(request.user):
        messages.error(request, "Admin access required.")
        return redirect('dashboard_redirect')

    search_q = request.GET.get('q', '').strip()
    student_type_filter = request.GET.get('type', '').strip()
    students = Student.objects.select_related('current_hostel', 'current_room', 'current_bed').all()

    if search_q:
        students = students.filter(
            models.Q(full_name__icontains=search_q) |
            models.Q(student_id__icontains=search_q) |
            models.Q(registration_number__icontains=search_q)
        )

    if student_type_filter in ['HOSTEL', 'DAY_SCHOLAR']:
        students = students.filter(student_type=student_type_filter)

    total_count = Student.objects.count()
    hostel_count = Student.objects.filter(student_type='HOSTEL').count()
    day_scholar_count = Student.objects.filter(student_type='DAY_SCHOLAR').count()

    context = {
        'students': students[:150],
        'total_count': total_count,
        'hostel_count': hostel_count,
        'day_scholar_count': day_scholar_count,
        'search_q': search_q,
        'selected_type': student_type_filter,
    }
    return render(request, 'admin_panel/students_manager.html', context)

@login_required
def admin_update_student_status(request, student_id):
    """
    Admin updates student fee status, disciplinary status, or account status.
    """
    if not verify_admin(request.user):
        messages.error(request, "Admin access required.")
        return redirect('dashboard_redirect')

    student = get_object_or_404(Student, id=student_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        new_val = request.POST.get('value')

        if action == 'fee_status' and new_val in ['PAID', 'PARTIAL', 'UNPAID']:
            student.fee_status = new_val
            student.save(update_fields=['fee_status'])
            messages.success(request, f"Fee status for {student.student_id} set to {new_val}.")

        elif action == 'disciplinary_status' and new_val in ['CLEAN', 'WARNING', 'HOLD']:
            student.disciplinary_status = new_val
            student.save(update_fields=['disciplinary_status'])
            messages.success(request, f"Disciplinary status for {student.student_id} set to {new_val}.")

        elif action == 'account_status' and new_val in ['ACTIVE', 'SUSPENDED', 'INACTIVE']:
            student.account_status = new_val
            student.save(update_fields=['account_status'])
            messages.success(request, f"Account status for {student.student_id} set to {new_val}.")

        elif action == 'deallocate_bed':
            if student.current_bed:
                old_bed = student.current_bed
                old_bed.status = 'VACANT'
                old_bed.save()
                BedAllocation.objects.filter(student=student, is_active=True).update(
                    is_active=False,
                    end_date=timezone.now(),
                    remarks="De-allocated by Admin"
                )
                student.current_bed = None
                student.current_room = None
                student.current_hostel = None
                student.student_type = 'DAY_SCHOLAR'
                student.save(update_fields=['current_bed', 'current_room', 'current_hostel', 'student_type'])
                messages.warning(request, f"Bed de-allocated for student {student.student_id}.")

    return redirect('admin_students_manager')
