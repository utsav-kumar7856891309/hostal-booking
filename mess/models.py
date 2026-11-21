from django.db import models

class MessMenu(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    MEAL_CHOICES = [
        ('BREAKFAST', 'Breakfast'),
        ('LUNCH', 'Lunch'),
        ('SNACKS', 'Evening Snacks'),
        ('DINNER', 'Dinner'),
    ]

    day_of_week = models.CharField(max_length=15, choices=DAY_CHOICES)
    meal_type = models.CharField(max_length=20, choices=MEAL_CHOICES)
    items = models.TextField(help_text="Comma-separated or newline-separated items")
    timings = models.CharField(max_length=50, help_text="e.g. 7:30 AM - 9:30 AM")
    is_special = models.BooleanField(default=False)

    class Meta:
        unique_together = ['day_of_week', 'meal_type']
        ordering = ['day_of_week', 'meal_type']

    def __str__(self):
        return f"{self.day_of_week} - {self.get_meal_type_display()}"

class MessRegistration(models.Model):
    DIET_CHOICES = [
        ('VEG', 'Vegetarian'),
        ('NON_VEG', 'Non-Vegetarian'),
        ('JAIN', 'Jain'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='mess_registrations')
    hostel = models.ForeignKey('hostels.Hostel', on_delete=models.CASCADE, related_name='mess_students')
    dietary_preference = models.CharField(max_length=20, choices=DIET_CHOICES, default='VEG')
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.student.student_id} -> {self.hostel.code} Mess ({self.dietary_preference})"

class ServiceFeedback(models.Model):
    SERVICE_CHOICES = [
        ('MESS', 'Mess / Food'),
        ('LAUNDRY', 'Laundry Service'),
        ('MAINTENANCE', 'Maintenance'),
        ('FACILITIES', 'Hostel Facilities'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='feedbacks')
    service_type = models.CharField(max_length=30, choices=SERVICE_CHOICES)
    rating = models.PositiveIntegerField(default=5, help_text="Rating out of 5")
    title = models.CharField(max_length=150)
    comments = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.service_type} Feedback ({self.rating}/5) by {self.student.student_id}"
