from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from PIL import Image


class User(AbstractUser):
    """Extend Django AbstractUser"""

    email = models.EmailField(unique=True)
    image = models.ImageField(default="default.jpg", upload_to="profile_pics")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username or self.email

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.image and self.image.name != "default.jpg":
            try:
                img = Image.open(self.image.path)
                if img.height > 300 or img.width > 300:
                    img.thumbnail((300, 300))
                    img.save(self.image.path)
            except (FileNotFoundError, OSError):
                pass


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


class HealthProfile(models.Model):
    DIABETES_TYPE_1 = "type1"
    DIABETES_TYPE_2 = "type2"

    DIABETES_TYPE_CHOICES = [(DIABETES_TYPE_1, "Type 1"), (DIABETES_TYPE_2, "Type 2")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_profile",
    )
    diabetes_type = models.CharField(
        max_length=10, choices=DIABETES_TYPE_CHOICES, default=DIABETES_TYPE_1
    )

    def __str__(self):
        return f"{self.user.username} profile"
