from decimal import Decimal
from django.db import models
from django.utils import timezone

class PolicyRule(models.Model):
    code = models.CharField(max_length=50, unique=True, default='DEFAULT')
    name = models.CharField(max_length=150, default='Standard University Exchange Policy')
    is_enabled = models.BooleanField(default=True)
    max_cycle_length = models.PositiveIntegerField(default=5, help_text="Maximum students in an exchange cycle (2 to 5)")
    allow_cross_hostel = models.BooleanField(default=True, help_text="Allow exchange between different hostels of same gender")
    allow_cross_category = models.BooleanField(default=True, help_text="Allow exchange between AC and Non-AC or different room categories")
    allow_cross_academic_year = models.BooleanField(default=True, help_text="Allow exchange between students of different academic years")
    allow_cross_course = models.BooleanField(default=True, help_text="Allow exchange between students of different degree courses")
    processing_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('200.00'), help_text="Fixed individual fee per student")
    proposal_expiry_hours = models.PositiveIntegerField(default=72, help_text="Hours before pending proposal expires automatically")
    cooling_off_days = models.PositiveIntegerField(default=30, help_text="Days a student must wait after a completed exchange before requesting another")
    max_exchanges_per_year = models.PositiveIntegerField(default=2)

    def __str__(self):
        return f"{self.name} (Max Cycle: {self.max_cycle_length}, Fee: ₹{self.processing_fee})"

    @classmethod
    def get_current(cls):
        policy, _ = cls.objects.get_or_create(
            code='DEFAULT',
            defaults={'name': 'Standard University Exchange Policy'}
        )
        return policy

class ExchangeRequest(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active / Looking for Match'),
        ('MATCHED', 'Proposal Created'),
        ('CANCELLED', 'Cancelled by Student'),
        ('COMPLETED', 'Exchange Completed'),
        ('EXPIRED', 'Expired'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='exchange_requests')
    current_bed = models.ForeignKey('rooms.Bed', on_delete=models.PROTECT, related_name='offered_in_requests')
    preferred_hostels = models.ManyToManyField('hostels.Hostel', blank=True, related_name='preferred_in_requests')
    preferred_categories = models.ManyToManyField('rooms.RoomCategory', blank=True, related_name='preferred_in_requests')
    preferred_floor = models.PositiveIntegerField(null=True, blank=True)
    specific_target_bed = models.ForeignKey('rooms.Bed', on_delete=models.SET_NULL, null=True, blank=True, related_name='targeted_in_requests')
    specific_target_student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='targeted_in_requests')
    reason = models.TextField(blank=True, help_text="Reason for exchange request")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Req #{self.id}: {self.student.student_id} from {self.current_bed.full_code} ({self.status})"

class ExchangeParticipant(models.Model):
    exchange_request = models.ForeignKey(ExchangeRequest, on_delete=models.CASCADE, related_name='participants')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, default='REQUESTER')

    def __str__(self):
        return f"{self.student.student_id} in Req #{self.exchange_request_id}"

class ExchangeProposal(models.Model):
    STATUS_CHOICES = [
        ('PROPOSED', 'Proposed / Pending Student Acceptances'),
        ('ACCEPTED_BY_ALL', 'Accepted by All Students'),
        ('PENDING_WARDEN_APPROVAL', 'Pending Warden Approval'),
        ('APPROVED_BY_WARDENS', 'Approved by Wardens'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('COMPLETED', 'Exchange Completed'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]

    proposal_code = models.CharField(max_length=50, unique=True, help_text="e.g. EXP-2026-0001")
    cycle_length = models.PositiveIntegerField(default=2, help_text="Number of students involved in cycle (2-5)")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PROPOSED')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.proposal_code} ({self.cycle_length}-way, {self.get_status_display()})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status in ['PROPOSED', 'ACCEPTED_BY_ALL', 'PENDING_WARDEN_APPROVAL', 'PAYMENT_PENDING']

    @property
    def all_participants_accepted(self):
        return not self.participants.filter(status='PENDING').exists() and not self.participants.filter(status='DECLINED').exists()

    @property
    def all_wardens_approved(self):
        return not self.warden_approvals.filter(status='PENDING').exists() and not self.warden_approvals.filter(status='REJECTED').exists() and self.warden_approvals.exists()

class ProposalParticipant(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Decision'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
    ]

    proposal = models.ForeignKey(ExchangeProposal, on_delete=models.CASCADE, related_name='participants')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='proposal_participations')
    from_bed = models.ForeignKey('rooms.Bed', on_delete=models.PROTECT, related_name='moves_from')
    to_bed = models.ForeignKey('rooms.Bed', on_delete=models.PROTECT, related_name='moves_to')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    accepted_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        unique_together = ['proposal', 'student']
        ordering = ['id']

    def __str__(self):
        return f"{self.student.student_id}: {self.from_bed.full_code} -> {self.to_bed.full_code} [{self.status}]"
