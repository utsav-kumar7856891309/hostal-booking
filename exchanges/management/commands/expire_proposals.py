from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from exchanges.models import ExchangeProposal, ExchangeRequest
from notifications.models import Notification
from audit.models import AuditEntry

class Command(BaseCommand):
    help = "Checks and marks expired exchange proposals that passed their expiration deadline without completion."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_proposals = ExchangeProposal.objects.filter(
            expires_at__lt=now,
            status__in=['PROPOSED', 'ACCEPTED_BY_ALL', 'PENDING_WARDEN_APPROVAL', 'PAYMENT_PENDING']
        )

        count = expired_proposals.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No pending proposals have expired."))
            return

        with transaction.atomic():
            for prop in expired_proposals:
                prop.status = 'EXPIRED'
                prop.save(update_fields=['status'])

                # Release requests back to ACTIVE
                for p in prop.participants.all():
                    ExchangeRequest.objects.filter(student=p.student, status='MATCHED').update(status='ACTIVE')

                    Notification.objects.create(
                        recipient=p.student.user,
                        title="Exchange Proposal Expired",
                        message=f"Proposal {prop.proposal_code} has expired because required actions were not completed within the deadline.",
                        notification_type='PROPOSAL_DECLINED',
                        link=f"/exchanges/proposals/{prop.id}/"
                    )

                AuditEntry.objects.create(
                    action='PROPOSAL_EXPIRED_AUTOMATICALLY',
                    entity_type='ExchangeProposal',
                    entity_id=str(prop.id),
                    description=f"Proposal {prop.proposal_code} expired automatically at {now}."
                )

        self.stdout.write(self.style.SUCCESS(f"Successfully processed and expired {count} exchange proposals."))
