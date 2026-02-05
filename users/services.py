from .models import UserPreferences, HealthProfile, User
from .forms import PreferencesForm, HealthProfileForm, ProfileUpdateForm


def get_user_preferences(user):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs


def get_health_profile(user):
    prefs, _ = HealthProfile.objects.get_or_create(user=user)
    return prefs


def handle_profile_form(request):
    if request.method == "POST":
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if p_form.is_valid():
            p_form.save()
            return p_form, True
        else:
            return p_form, False
    else:
        form = ProfileUpdateForm(instance=request.user)
        return form, False
        

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


def handle_health_profile_form(request):
    prefs, _ = HealthProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = HealthProfileForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            return form, True
        else:
            return form, False

    else:
        form = HealthProfileForm(instance=prefs)
        return form, False

