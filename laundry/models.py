from decimal import Decimal
from django.db import models

class LaundryService(models.Model):
    service_name = models.CharField(max_length=100, help_text="e.g. Regular Wash & Fold, Ironing, Dry Cleaning")
    rate_per_unit = models.DecimalField(max_digits=8, decimal_places=2)
    unit_type = models.CharField(max_length=30, default='Per Kg', help_text="e.g. Per Kg, Per Piece")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.service_name} (₹{self.rate_per_unit} {self.unit_type})"

class LaundryRequest(models.Model):
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('ACCEPTED', 'Accepted'),
        ('COLLECTED', 'Collected'),
        ('PROCESSING', 'Processing'),
        ('READY', 'Ready for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]

    booking_id = models.CharField(max_length=30, unique=True, help_text="e.g. LND-2026-0001")
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='laundry_requests')
    hostel = models.ForeignKey('hostels.Hostel', on_delete=models.CASCADE, related_name='laundry_requests')
    service = models.ForeignKey(LaundryService, on_delete=models.PROTECT)
    item_count_or_weight = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.0'))
    pickup_slot = models.DateTimeField()
    delivery_slot = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED')
    special_instructions = models.TextField(blank=True)
    total_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.booking_id} - {self.student.student_id} ({self.status})"
