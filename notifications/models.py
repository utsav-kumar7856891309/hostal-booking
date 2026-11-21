from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPE_CHOICES = [
        ('PROPOSAL_NEW', 'New Exchange Proposal'),
        ('PROPOSAL_ACCEPTED', 'Proposal Accepted by Peer'),
        ('PROPOSAL_DECLINED', 'Proposal Declined'),
        ('WARDEN_DECISION', 'Warden Approval Decision'),
        ('PAYMENT_REQUIRED', 'Payment Required'),
        ('EXCHANGE_COMPLETED', 'Exchange Completed'),
        ('SERVICE_UPDATE', 'Service Request Update'),
        ('ANNOUNCEMENT', 'Hostel Announcement'),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='PROPOSAL_NEW')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"To: {self.recipient.username} | {self.title} [{'Read' if self.is_read else 'Unread'}]"
