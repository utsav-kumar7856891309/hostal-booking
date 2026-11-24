from django.db import models
from django.conf import settings

class Student(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]

    FEE_STATUS_CHOICES = [
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partial'),
        ('UNPAID', 'Unpaid'),
    ]

    DISCIPLINARY_CHOICES = [
        ('CLEAN', 'Clean Record'),
        ('WARNING', 'Warning Issued'),
        ('HOLD', 'Disciplinary Hold'),
    ]

    ACCOUNT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('INACTIVE', 'Inactive'),
    ]

    STUDENT_TYPE_CHOICES = [
        ('HOSTEL', 'Hostel Resident'),
        ('DAY_SCHOLAR', 'Day Scholar'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=30, unique=True, help_text="e.g. STU2026001")
    registration_number = models.CharField(max_length=30, unique=True, help_text="e.g. REG2026001 or 12313714")
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=20)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_photograph = models.ImageField(upload_to='students/', blank=True, null=True)

    student_type = models.CharField(
        max_length=20,
        choices=STUDENT_TYPE_CHOICES,
        default='HOSTEL',
        help_text="Designation in Central University Database (Hostel Resident or Day Scholar)"
    )

    course = models.CharField(max_length=100, help_text="e.g. B.Tech Computer Science")
    department = models.CharField(max_length=100)
    academic_year = models.CharField(max_length=20, help_text="e.g. 1st Year, 2nd Year, 3rd Year, 4th Year")
    admission_year = models.PositiveIntegerField(default=2024)

    current_hostel = models.ForeignKey('hostels.Hostel', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    current_room = models.ForeignKey('rooms.Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='occupants')
    current_bed = models.ForeignKey('rooms.Bed', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_occupant')

    fee_status = models.CharField(max_length=20, choices=FEE_STATUS_CHOICES, default='PAID')
    disciplinary_status = models.CharField(max_length=20, choices=DISCIPLINARY_CHOICES, default='CLEAN')
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['student_id']

    def __str__(self):
        bed_str = self.current_bed.full_code if self.current_bed else "Day Scholar"
        return f"{self.full_name} ({self.registration_number}) [{self.get_student_type_display()}]"

    @property
    def is_day_scholar(self):
        return self.student_type == 'DAY_SCHOLAR' or self.current_bed is None

    @property
    def is_hostel_resident(self):
        return self.student_type == 'HOSTEL' and self.current_bed is not None

    @property
    def is_eligible_for_exchange(self):
        """Check student eligibility according to core rules"""
        if self.account_status != 'ACTIVE':
            return False, "Account is not active."
        if self.disciplinary_status == 'HOLD':
            return False, "Disciplinary hold on record."
        if self.fee_status == 'UNPAID':
            return False, "Hostel fees unpaid."
        if not self.current_bed:
            return False, "No active bed allocation found."
        return True, "Eligible"
