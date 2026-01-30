from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from .models import User
  
from django import forms
from .models import UserPreferences

class CustomUserCreationForm(AdminUserCreationForm):
  usable_password = None

  # remove help text
  def __init__(self, *args, **kwargs):
    super(AdminUserCreationForm, self).__init__(*args, **kwargs)
    for fieldname in ["username", "password1", "password2"]:
        self.fields[fieldname].help_text = None
    self.fields["password2"].label = "Confirm Password"
    
  class Meta:
    model = User
    fields = ("username", "email")
    
    
class CustomUserChangeForm(UserChangeForm):
  
  class Meta:
    model = User
    fields = ("username", "email")


class PreferencesForm(forms.ModelForm):
  class Meta:
    model = UserPreferences
    fields = ["glucose_unit"]
    labels = {
      "glucose_unit": "Glucose Unit"
    }