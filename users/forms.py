from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from .models import User

from django import forms
from .models import UserPreferences, HealthProfile


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


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'image']

class PreferencesForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = ["glucose_unit"]
        labels = {"glucose_unit": "Glucose Unit"}


class HealthProfileForm(forms.ModelForm):
    class Meta:
        model = HealthProfile
        fields = ["diabetes_type"]
        labels = {"diabetes_type": "Diabetes Type"}
