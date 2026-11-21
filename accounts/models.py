from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        WARDEN = 'WARDEN', 'Hostel Warden'
        CHIEF_WARDEN = 'CHIEF_WARDEN', 'Chief Warden'
        ADMIN = 'ADMIN', 'University Administrator'
        DEAN = 'DEAN', 'Dean of Student Welfare'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="Role determining platform permissions."
    )
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_warden(self):
        return self.role == self.Role.WARDEN

    @property
    def is_chief_warden(self):
        return self.role == self.Role.CHIEF_WARDEN

    @property
    def is_admin_user(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_dean(self):
        return self.role == self.Role.DEAN

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
