from decimal import Decimal
from django.db import models
from django.db.models import Q
from django.utils import timezone

class BedAllocation(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='bed_allocations')
    bed = models.ForeignKey('rooms.Bed', on_delete=models.CASCADE, related_name='allocations')
    academic_year = models.CharField(max_length=20, default='2026-2027')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(
                fields=['student'],
                condition=Q(is_active=True),
                name='unique_active_student_allocation'
            ),
            models.UniqueConstraint(
                fields=['bed'],
                condition=Q(is_active=True),
                name='unique_active_bed_allocation'
            ),
        ]

    def __str__(self):
        status = "Active" if self.is_active else "Historical"
        return f"{self.student.student_id} -> {self.bed.full_code} ({status})"

class RoomBooking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment/Verification'),
        ('CONFIRMED', 'Confirmed & Allotted'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
    ]

    booking_id = models.CharField(max_length=50, unique=True, help_text="e.g. BKG-2026-0001")
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='direct_bookings')
    bed = models.ForeignKey('rooms.Bed', on_delete=models.PROTECT, related_name='bookings')
    academic_year = models.CharField(max_length=20, default='2026-2027')
    annual_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED')
    booking_date = models.DateTimeField(default=timezone.now)
    remarks = models.TextField(blank=True)
    transaction = models.ForeignKey('finance.FinancialTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='booking_record')

    class Meta:
        ordering = ['-booking_date']

    def __str__(self):
        return f"{self.booking_id} - {self.student.full_name} -> {self.bed.full_code} ({self.status})"
