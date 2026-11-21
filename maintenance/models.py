from django.db import models

class MaintenanceRequest(models.Model):
    CATEGORY_CHOICES = [
        ('ELECTRICAL', 'Electrical Problem'),
        ('PLUMBING', 'Plumbing Problem'),
        ('FURNITURE', 'Furniture Damage'),
        ('AC', 'Air Conditioning Issue'),
        ('WIFI', 'Wi-Fi / Internet Problem'),
        ('HOUSEKEEPING', 'Housekeeping / Cleaning'),
        ('GENERAL', 'General Maintenance'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('REPORTED', 'Reported'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CANCELLED', 'Cancelled'),
    ]

    complaint_id = models.CharField(max_length=30, unique=True, help_text="e.g. MNT-2026-0001")
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='maintenance_requests')
    hostel = models.ForeignKey('hostels.Hostel', on_delete=models.CASCADE, related_name='maintenance_requests')
    room = models.ForeignKey('rooms.Room', on_delete=models.CASCADE, related_name='maintenance_requests')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=150)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    photograph = models.ImageField(upload_to='maintenance/', blank=True, null=True)
    assigned_staff = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REPORTED')
    resolution_remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.complaint_id} - [{self.category}] {self.title} ({self.status})"
