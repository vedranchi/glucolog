from .models import UserPreferences
from .forms import PreferencesForm

def get_user_preferences(user):
  prefs, _ = UserPreferences.objects.get_or_create(user=user)
  return prefs

def handle_preferences_form(request):
  prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
  
  if request.method == "POST":
    form = PreferencesForm(request.POST, instance=prefs)
    if form.is_valid():
      form.save()
      return form, True
    else:
      return form, False
    
  else:
    form = PreferencesForm(instance=prefs)
    return form, False