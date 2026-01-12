from django import forms
from .models import GlucoseLog, MealLog

class GlucoseLogForm(forms.ModelForm):
  class Meta:
    model = GlucoseLog
    fields = ["value", "measured_at", "note"]
    