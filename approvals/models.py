from django.db import models
from django.conf import settings

class WardenApproval(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Decision'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    proposal = models.ForeignKey('exchanges.ExchangeProposal', on_delete=models.CASCADE, related_name='warden_approvals')
    warden = models.ForeignKey('hostels.Warden', on_delete=models.PROTECT, related_name='approvals', null=True, blank=True)
    hostel = models.ForeignKey('hostels.Hostel', on_delete=models.PROTECT, related_name='approvals')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    remarks = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['proposal', 'hostel']
        ordering = ['created_at']

    def __str__(self):
        warden_str = self.warden.user.username if self.warden else "Any Assigned Warden"
        return f"Proposal {self.proposal.proposal_code} - {self.hostel.code}: {self.status} ({warden_str})"
