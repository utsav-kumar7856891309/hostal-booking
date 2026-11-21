from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from students.models import Student
from finance.models import StudentAccount
from audit.models import AuditEntry

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Invalid username or password. Please check your credentials.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})

def register_view(request):
    """
    Allows a new student to register an account on the HostelX platform.
    Automatically initializes Student profile and StudentAccount.
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        gender = request.POST.get('gender', 'Male')
        course = request.POST.get('course', 'B.Tech Computer Science')
        department = request.POST.get('department', 'Engineering')
        academic_year = request.POST.get('academic_year', '1st Year')
        admission_year = request.POST.get('admission_year', 2026)

        # Basic validations
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return render(request, 'accounts/register.html')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/register.html')

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return render(request, 'accounts/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken. Please choose another.")
            return render(request, 'accounts/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, f"Email '{email}' is already registered.")
            return render(request, 'accounts/register.html')

        with transaction.atomic():
            # 1. Create User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.STUDENT,
                phone_number=phone
            )

            # Generate unique student ID and registration number
            timestamp_suffix = timezone.now().strftime('%y%m%d%H%M')
            stu_id = f"STU2026_{username.upper()}"
            reg_no = f"REG2026_{username.upper()}"

            # 2. Create Student profile (unallocated initially)
            student = Student.objects.create(
                user=user,
                student_id=stu_id,
                registration_number=reg_no,
                full_name=f"{first_name} {last_name}".strip() or username,
                email=email,
                mobile_number=phone,
                gender=gender,
                course=course,
                department=department,
                academic_year=academic_year,
                admission_year=int(admission_year) if admission_year else 2026,
                fee_status='PAID',
                disciplinary_status='CLEAN',
                account_status='ACTIVE'
            )

            # 3. Create StudentAccount
            StudentAccount.objects.create(
                student=student,
                balance=Decimal('0.00'),
                outstanding_due=Decimal('0.00')
            )

            # 4. Audit Log
            AuditEntry.objects.create(
                actor=user,
                action='STUDENT_REGISTRATION',
                entity_type='Student',
                entity_id=str(student.id),
                description=f"New student {student.full_name} ({student.student_id}) registered successfully."
            )

            # Auto-login newly registered student
            login(request, user)
            messages.success(request, f"Registration successful! Welcome to HostelX, {student.full_name}. You can now book your hostel room below.")
            return redirect('room_booking_catalog')

    return render(request, 'accounts/register.html')

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
