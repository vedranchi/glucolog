from django import forms
from .models import UserPreferences

class PreferencesForm(forms.ModelForm):
  class Meta:
    model = UserPreferences
    fields = ["glucose_unit"]
    labels = {
      "glucose_unit": "Glucose Unit"
    }