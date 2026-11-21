from django.db import models
from django.conf import settings

class University(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Universities'

    def __str__(self):
        return f"{self.name} ({self.code})"

class Hostel(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]

    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name='hostels')
    code = models.CharField(max_length=20, unique=True, help_text="e.g. H001, H002, H003, H004")
    name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    address = models.TextField(blank=True)
    total_floors = models.PositiveIntegerField(default=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.gender}"

    @property
    def total_rooms_count(self):
        return self.rooms.count()

    @property
    def total_beds_count(self):
        return sum(room.beds.count() for room in self.rooms.all())

    @property
    def occupied_beds_count(self):
        return sum(room.beds.filter(status='OCCUPIED').count() for room in self.rooms.all())

    @property
    def vacant_beds_count(self):
        return sum(room.beds.filter(status='VACANT').count() for room in self.rooms.all())

class Warden(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='warden_profile')
    hostel = models.ForeignKey(Hostel, on_delete=models.SET_NULL, null=True, blank=True, related_name='wardens')
    is_chief = models.BooleanField(default=False)
    office_room = models.CharField(max_length=50, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        title = "Chief Warden" if self.is_chief else f"Warden - {self.hostel.name if self.hostel else 'Unassigned'}"
        return f"{self.user.get_full_name() or self.user.username} ({title})"

class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    title = models.CharField(max_length=255)
    content = models.TextField()
    target_hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, null=True, blank=True, related_name='announcements', help_text="Leave blank for all hostels.")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='NORMAL')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        hostel_str = self.target_hostel.name if self.target_hostel else "All Hostels"
        return f"[{self.priority}] {self.title} ({hostel_str})"
