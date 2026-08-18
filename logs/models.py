from django.db import models
from django.conf import settings
from django.utils import timezone


class InsulinLog(models.Model):
    INSULIN_TYPES = [("basal", "Basal"), ("bolus", "Bolus")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    insulin_type = models.CharField(max_length=10, choices=INSULIN_TYPES)
    units = models.DecimalField(max_digits=4, decimal_places=1)
    brand = models.CharField(max_length=50, blank=True, null=True)
    taken_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True, null=True)

    # soft delete — records are flagged rather than removed
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        # Deliberately free of measurements and identity. __str__ is what error
        # reporters, tracebacks and admin LogEntry.object_repr capture, and none
        # of those are places a patient's dose should end up. The pk is enough
        # to look the record up deliberately.
        return f"InsulinLog #{self.pk}"


class GlucoseLog(models.Model):
    CONTEXT = [
        ("fasting", "Fasting"),
        ("before meal", "Before meal"),
        ("after meal", "After meal"),
        ("bedtime", "Bedtime"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # value is always stored in mmol/L; convert on read for mg/dL users
    value = models.DecimalField(max_digits=4, decimal_places=1)
    note = models.CharField(max_length=255, blank=True, null=True)
    context = models.CharField(max_length=20, choices=CONTEXT, default="other")
    measured_at = models.DateTimeField(default=timezone.now)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        # No glucose value here — see the note on InsulinLog.__str__.
        return f"GlucoseLog #{self.pk}"


class MealLog(models.Model):
    CONTEXT = [
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("dinner", "Dinner"),
        ("snack", "Snack"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    note = models.CharField(max_length=255, blank=True, null=True)
    # nutrition fields are all optional — user may log a meal without full macro data
    carbs = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    protein = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    fats = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    calories = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    eaten_at = models.DateTimeField(default=timezone.now)
    context = models.CharField(max_length=20, choices=CONTEXT, default="breakfast")

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        # No meal detail here — see the note on InsulinLog.__str__.
        return f"MealLog #{self.pk}"
