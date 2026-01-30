from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class User(AbstractUser):
    """Extend Django AbstractUser"""

    email = models.EmailField(unique=True)

    # extend later

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username or self.email


# manage user settings
class UserPreferences(models.Model):
    GLUCOSE_UNIT_MMOL = "mmol"
    GLUCOSE_UNIT_MGDL = "mg/dL"

    GLUCOSE_UNIT_CHOICES = [
        (GLUCOSE_UNIT_MMOL, "mmol/L"),
        (GLUCOSE_UNIT_MGDL, "mg/dL"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences"
    )
    glucose_unit = models.CharField(
        max_length=10, choices=GLUCOSE_UNIT_CHOICES, default=GLUCOSE_UNIT_MMOL
    )

    def __str__(self):
        return f"{self.user.username} profile"
