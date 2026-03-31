from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User

class CustomUserAdmin(UserAdmin):
  add_form = CustomUserCreationForm
  form = CustomUserChangeForm
  model = User
  list_display = [
    "email",
    "username",
    "image",
    "is_staff",
    "is_active",
  ]
  fieldsets = UserAdmin.fieldsets + (
    ('Profile', {'fields': ('image',)}),
  )
  
  add_fieldsets = UserAdmin.add_fieldsets + (
    ('Profile', {'fields': ('image',)}),
  )
  
admin.site.register(User, CustomUserAdmin)
  