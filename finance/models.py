from decimal import Decimal
from django.db import models
from django.utils import timezone

class StudentAccount(models.Model):
    student = models.OneToOneField('students.Student', on_delete=models.CASCADE, related_name='financial_account')
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Advance balance generated from lower-fee room exchanges, available for next year's fees."
    )
    outstanding_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Unpaid fees or pending room difference charges."
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.student_id} Account | Advance: ₹{self.balance} | Due: ₹{self.outstanding_due}"

class FinancialTransaction(models.Model):
    TYPE_CHOICES = [
        ('PROCESSING_FEE', 'Exchange Processing Fee'),
        ('ROOM_FEE_DIFFERENCE', 'Room Fee Difference'),
        ('ADVANCE_CREDIT', 'Advance Credit (Excess Room Fee)'),
        ('SIMULATED_PAYMENT', 'Simulated Payment (Test Transaction)'),
        ('ANNUAL_FEE_PAYMENT', 'Annual Hostel Fee Payment'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='transactions')
    proposal = models.ForeignKey('exchanges.ExchangeProposal', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reference_id = models.CharField(max_length=50, unique=True, help_text="e.g. TXN-2026-0001")
    is_simulated = models.BooleanField(default=True, help_text="Explicitly identified as a test transaction. No real money collected.")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference_id} | {self.student.student_id} | ₹{self.amount} ({self.get_transaction_type_display()}) [{self.status}]"

class FinancialLedgerEntry(models.Model):
    ENTRY_CHOICES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]

    account = models.ForeignKey(StudentAccount, on_delete=models.CASCADE, related_name='ledger_entries')
    transaction = models.ForeignKey(FinancialTransaction, on_delete=models.CASCADE, related_name='ledger_entries')
    entry_type = models.CharField(max_length=10, choices=ENTRY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Financial Ledger Entries'

    def __str__(self):
        return f"{self.account.student.student_id} | {self.entry_type} ₹{self.amount} | Bal: ₹{self.balance_after}"

class TransferRecord(models.Model):
    transfer_id = models.CharField(max_length=50, unique=True, help_text="e.g. TR-2026-0001")
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='transfer_records')
    proposal = models.ForeignKey('exchanges.ExchangeProposal', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_records')

    previous_hostel = models.ForeignKey('hostels.Hostel', on_delete=models.PROTECT, related_name='+')
    previous_room = models.ForeignKey('rooms.Room', on_delete=models.PROTECT, related_name='+')
    previous_bed = models.ForeignKey('rooms.Bed', on_delete=models.PROTECT, related_name='+')
    previous_category = models.ForeignKey('rooms.RoomCategory', on_delete=models.PROTECT, related_name='+')

    new_hostel = models.ForeignKey('hostels.Hostel', on_delete=models.PROTECT, related_name='+')
    new_room = models.ForeignKey('rooms.Room', on_delete=models.PROTECT, related_name='+')
    new_bed = models.ForeignKey('rooms.Bed', on_delete=models.PROTECT, related_name='+')
    new_category = models.ForeignKey('rooms.RoomCategory', on_delete=models.PROTECT, related_name='+')

    previous_annual_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    new_annual_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    fee_difference = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    advance_balance_generated = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    approved_by_summary = models.TextField(blank=True, help_text="Summary of wardens and timestamps who approved")
    transfer_date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-transfer_date']

    def __str__(self):
        return f"{self.transfer_id} - {self.student.full_name}: {self.previous_bed.full_code} -> {self.new_bed.full_code}"
