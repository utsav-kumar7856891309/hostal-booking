from django.db import models

class RoomCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g. AC Single Occupancy")
    is_ac = models.BooleanField(default=True)
    capacity = models.PositiveIntegerField(help_text="Total bed capacity")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Room Categories'
        ordering = ['name']

    def __str__(self):
        ac_str = "AC" if self.is_ac else "Non-AC"
        return f"{self.name} ({ac_str}, Cap: {self.capacity})"

class Room(models.Model):
    hostel = models.ForeignKey('hostels.Hostel', on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=20, help_text="Unique room number within hostel, e.g. A101")
    floor = models.PositiveIntegerField(default=1)
    category = models.ForeignKey(RoomCategory, on_delete=models.PROTECT, related_name='rooms')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['hostel', 'room_number']
        ordering = ['hostel', 'floor', 'room_number']

    def __str__(self):
        return f"{self.hostel.code}-{self.room_number} ({self.category.name})"

    @property
    def occupied_count(self):
        return self.beds.filter(status='OCCUPIED').count()

    @property
    def is_full(self):
        return self.occupied_count >= self.category.capacity

class Bed(models.Model):
    STATUS_CHOICES = [
        ('VACANT', 'Vacant'),
        ('OCCUPIED', 'Occupied'),
        ('BLOCKED', 'Blocked'),
        ('MAINTENANCE', 'Maintenance'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='beds')
    bed_identifier = models.CharField(max_length=20, help_text="e.g. Bed 1, Bed 2 or B1, B2")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='VACANT')

    class Meta:
        unique_together = ['room', 'bed_identifier']
        ordering = ['room', 'bed_identifier']

    def __str__(self):
        return f"{self.room.hostel.code}-{self.room.room_number}-{self.bed_identifier}"

    @property
    def full_code(self):
        return f"{self.room.hostel.code}-{self.room.room_number}-{self.bed_identifier}"

class RoomPricing(models.Model):
    hostel = models.ForeignKey('hostels.Hostel', on_delete=models.CASCADE, related_name='pricings')
    category = models.ForeignKey(RoomCategory, on_delete=models.CASCADE, related_name='pricings')
    academic_year = models.CharField(max_length=20, default='2026-2027')
    annual_fee = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['hostel', 'category', 'academic_year']
        ordering = ['hostel', 'category']

    def __str__(self):
        return f"{self.hostel.code} | {self.category.name} | {self.academic_year}: ₹{self.annual_fee}"
