from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.utils import timezone

from accounts.models import User
from students.models import Student
from finance.models import StudentAccount
from audit.models import AuditEntry

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        login_id = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        portal = request.POST.get('portal', 'hostel_booking')

        if not login_id or not password:
            messages.error(request, "Please enter your User ID / Registration Number and Password.")
            return render(request, 'accounts/login.html')

        # 1. Resolve login_id (Registration Number, Student ID, Email, or Username)
        target_username = login_id

        if not User.objects.filter(username__iexact=login_id).exists():
            student = Student.objects.filter(
                models.Q(registration_number__iexact=login_id) |
                models.Q(student_id__iexact=login_id) |
                models.Q(email__iexact=login_id)
            ).select_related('user').first()

            if student and student.user:
                target_username = student.user.username
            else:
                user_by_email = User.objects.filter(email__iexact=login_id).first()
                if user_by_email:
                    target_username = user_by_email.username

        user = authenticate(request, username=target_username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact the University Administration.")
                return render(request, 'accounts/login.html')

            login(request, user)

            if user.is_student:
                student = getattr(user, 'student_profile', None)
                if portal == 'fee_accounts':
                    return redirect('my_financial_account')
                else:
                    return redirect('student_dashboard')
            else:
                return redirect('dashboard_redirect')
        else:
            messages.error(request, "Invalid User ID / Registration Number or Password. Please re-check or use quick demo fill.")
            return render(request, 'accounts/login.html')

    return render(request, 'accounts/login.html')

def register_view(request):
    """
    Public student self-registration is disabled.
    Only pre-registered university students in the Central University Database can access the platform.
    """
    messages.info(
        request,
        "Public student sign-up is disabled. All students are pre-enrolled in the Central University Database. "
        "Please log in using your University Registration Number (e.g. 12313714)."
    )
    return redirect('login')

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')

@login_required
def dashboard_redirect(request):
    """
    Directs the user to their designated role dashboard.
    """
    user = request.user
    if user.is_student:
        return redirect('student_dashboard')
    elif user.is_warden:
        return redirect('warden_dashboard')
    elif user.is_chief_warden:
        return redirect('chief_warden_dashboard')
    elif user.is_admin_user:
        return redirect('admin_dashboard')
    elif user.is_dean:
        return redirect('dean_dashboard')
    else:
        return redirect('user_profile')

@login_required
def user_profile(request):
    return render(request, 'accounts/profile.html')
