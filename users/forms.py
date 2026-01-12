from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from .models import User

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
    