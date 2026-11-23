from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from students.models import Student
from rooms.models import RoomPricing, Bed, RoomCategory
from hostels.models import Hostel, Announcement
from exchanges.models import ExchangeRequest, ExchangeProposal, ProposalParticipant, PolicyRule
from exchanges.services import create_direct_proposal, validate_student_eligibility
from finance.models import StudentAccount
from notifications.models import Notification

@login_required
def student_dashboard(request):
    user = request.user
    student = getattr(user, 'student_profile', None)
    if not student:
        messages.error(request, "Student profile not found for this user account.")
        return redirect('user_profile')

    # Current Room Pricing
    annual_fee = None
    if student.current_bed and student.current_room and student.current_hostel:
        pricing = RoomPricing.objects.filter(
            hostel=student.current_hostel,
            category=student.current_room.category,
            is_active=True
        ).first()
        if pricing:
            annual_fee = pricing.annual_fee

    # Student Account
    account, _ = StudentAccount.objects.get_or_create(student=student)

    # Active Requests
    active_requests = ExchangeRequest.objects.filter(student=student).exclude(status__in=['COMPLETED', 'CANCELLED', 'EXPIRED'])

    # Proposals involving this student
    participations = ProposalParticipant.objects.filter(student=student).select_related('proposal').order_by('-proposal__created_at')

    # Transfer Records
    transfer_records = student.transfer_records.select_related(
        'previous_hostel', 'previous_room', 'previous_bed',
        'new_hostel', 'new_room', 'new_bed'
    ).order_by('-transfer_date')

    # Announcements
    announcements = Announcement.objects.filter(
        is_active=True
    ).filter(
        target_hostel__in=[student.current_hostel, None]
    )[:5]

    # Warden / Admin Messages (notifications of type ANNOUNCEMENT sent to this student)
    warden_messages = Notification.objects.filter(
        recipient=user,
        notification_type='ANNOUNCEMENT'
    ).order_by('-created_at')[:8]

    # Eligibility Check
    is_eligible, eligibility_msg = validate_student_eligibility(student)

    context = {
        'student': student,
        'annual_fee': annual_fee,
        'account': account,
        'active_requests': active_requests,
        'participations': participations,
        'transfer_records': transfer_records,
        'announcements': announcements,
        'warden_messages': warden_messages,
        'is_eligible': is_eligible,
        'eligibility_msg': eligibility_msg,
    }
    return render(request, 'dashboards/student_dashboard.html', context)

@login_required
def create_exchange_request(request):
    user = request.user
    student = getattr(user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students can submit exchange requests.")
        return redirect('dashboard_redirect')

    policy = PolicyRule.get_current()
    is_eligible, reason = validate_student_eligibility(student, policy)
    if not is_eligible:
        messages.error(request, f"Eligibility validation failed: {reason}")
        return redirect('student_dashboard')

    if request.method == 'POST':
        preferred_hostel_ids = request.POST.getlist('preferred_hostels')
        preferred_cat_ids = request.POST.getlist('preferred_categories')
        preferred_floor = request.POST.get('preferred_floor')
        reason_text = request.POST.get('reason', '')
        target_bed_id = request.POST.get('specific_target_bed')

        req_obj = ExchangeRequest.objects.create(
            student=student,
            current_bed=student.current_bed,
            preferred_floor=int(preferred_floor) if preferred_floor else None,
            specific_target_bed_id=int(target_bed_id) if target_bed_id else None,
            reason=reason_text,
            status='ACTIVE'
        )

        if preferred_hostel_ids:
            req_obj.preferred_hostels.set(preferred_hostel_ids)
        if preferred_cat_ids:
            req_obj.preferred_categories.set(preferred_cat_ids)

        messages.success(request, f"Exchange request #{req_obj.id} submitted successfully! Our matching engine will monitor candidate beds.")
        return redirect('student_dashboard')

    # Same gender hostels only!
    eligible_hostels = Hostel.objects.filter(gender=student.gender)
    all_categories = RoomCategory.objects.all()

    context = {
        'student': student,
        'hostels': eligible_hostels,
        'categories': all_categories,
        'policy': policy,
    }
    return render(request, 'exchanges/create_request.html', context)

@login_required
def propose_direct_exchange(request):
    user = request.user
    student = getattr(user, 'student_profile', None)
    if not student:
        messages.error(request, "Only students can propose exchanges.")
        return redirect('dashboard_redirect')

    policy = PolicyRule.get_current()
    is_eligible, reason = validate_student_eligibility(student, policy)
    if not is_eligible:
        messages.error(request, f"Eligibility validation failed: {reason}")
        return redirect('student_dashboard')

    if request.method == 'POST':
        target_student_id = request.POST.get('target_student_id')
        remarks = request.POST.get('remarks', '')

        if not target_student_id:
            messages.error(request, "Please select an exchange partner.")
            return redirect('propose_direct_exchange')

        target_student = get_object_or_404(Student, id=target_student_id)

        proposal, msg = create_direct_proposal(student, target_student, remarks=remarks)
        if proposal:
            messages.success(request, f"Direct exchange proposal {proposal.proposal_code} created successfully! Awaiting peer acceptance.")
            return redirect('proposal_detail', proposal_id=proposal.id)
        else:
            messages.error(request, f"Could not create proposal: {msg}")

    # Eligible partners list (Same gender, currently allocated, active, exclude self)
    candidate_students = Student.objects.filter(
        gender=student.gender,
        account_status='ACTIVE',
        disciplinary_status__in=['CLEAN', 'WARNING'],
        fee_status__in=['PAID', 'PARTIAL'],
        current_bed__isnull=False
    ).exclude(id=student.id).select_related('current_hostel', 'current_room', 'current_bed', 'current_room__category')[:100]

    target_param = request.GET.get('target')
    selected_target_id = int(target_param) if target_param and target_param.isdigit() else None

    context = {
        'student': student,
        'candidates': candidate_students,
        'policy': policy,
        'selected_target_id': selected_target_id,
    }
    return render(request, 'exchanges/propose_direct.html', context)
