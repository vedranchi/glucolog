from django.db import models
from core.settings import AUTH_USER_MODEL
from django.utils import timezone

class InsulinLog(models.Model):
  # insulin types
  INSULIN_TYPES = [
    ('basal', 'Basal'),
    ('bolus', 'Bolus')
  ]
  
  user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
  insulin_type = models.CharField(max_length=10, choices=INSULIN_TYPES)
  units = models.DecimalField(max_digits=4, decimal_places=1)
  brand = models.CharField(max_length=50, blank=True, null=True)
  taken_at = models.DateTimeField(default=timezone.now)
  note = models.CharField(max_length=255, blank=True, null=True)
  
  is_deleted = models.BooleanField(default=False)
  deleted_at = models.DateTimeField(null=True, blank=True)
  
class GlucoseLog(models.Model):
  # glucose reading periods
  CONTEXT = [
    ('fasting', 'Fasting'),
    ('before meal', 'Before meal'),
    ('after meal', 'After meal'),
    ('bedtime', 'Bedtime'),
    ('other', 'Other'),
  ]
  user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
  value = models.DecimalField(max_digits=4, decimal_places=1)
  note = models.CharField(max_length=255, blank=True, null=True)
  context = models.CharField(max_length=20, choices=CONTEXT, default="other")
  measured_at = models.DateTimeField(default=timezone.now)
  
  is_deleted = models.BooleanField(default=False)
  deleted_at = models.DateTimeField(null=True, blank=True)
  
  def __str__(self):
    return f"{self.user} - {self.value} mmol/L @ {self.measured_at}"
  
class MealLog(models.Model):
  CONTEXT = [
    ('breakfast', 'Breakfast'),
    ('lunch', 'Lunch'),
    ('dinner', 'Dinner'),
    ('snack', 'Snack')
  ]
  note = models.CharField(max_length=255, blank=True, null=True)
  user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
  carbs = models.DecimalField(max_digits=5, decimal_places = 1, null=True, blank=True)
  protein = models.DecimalField(max_digits=5, decimal_places = 1, null=True, blank=True)
  fats = models.DecimalField(max_digits=5, decimal_places = 1, null=True, blank=True)
  calories = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
  eaten_at = models.DateTimeField(default=timezone.now) 
  context = models.CharField(max_length=20, choices=CONTEXT, default='breakfast')
  
  is_deleted = models.BooleanField(default=False)
  deleted_at = models.DateTimeField(null=True, blank=True)