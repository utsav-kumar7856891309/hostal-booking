from django.db import models

class Facility(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, help_text="e.g. Sports, Study, Recreation, IT")
    description = models.TextField()
    location = models.CharField(max_length=100, default='Central Facility / All Hostels')
    timings = models.CharField(max_length=100, default='6:00 AM - 10:00 PM')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Facilities'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.category})"
