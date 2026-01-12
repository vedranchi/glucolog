from django.db import models
from django.conf import settings

# manage user settings
class UserPreferences(models.Model):
  user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
  glucose_unit = models.CharField(max_length=10, choices=[('mmol', 'mmol/L'), ('mg/dL', 'mg/dL')], default='mmol')
  
  def __str__(self):
    return f"{self.user.username} profile"