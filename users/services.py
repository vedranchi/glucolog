from .models import UserPreferences, HealthProfile, User
from .forms import PreferencesForm, HealthProfileForm, ProfileUpdateForm


def get_user_preferences(user):
    # get_or_create ensures a preferences row always exists, even for legacy accounts
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs


def get_health_profile(user):
    prefs, _ = HealthProfile.objects.get_or_create(user=user)
    return prefs


def handle_profile_form(request):
    if request.method == "POST":
        return ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
    return ProfileUpdateForm(instance=request.user)


def handle_preferences_form(request):
    prefs, _ = UserPreferences.objects.get_or_create(user=request.user)

    if request.method == "POST":
        return PreferencesForm(request.POST, instance=prefs)
    return PreferencesForm(instance=prefs)


def handle_health_profile_form(request):
    prefs, _ = HealthProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        return HealthProfileForm(request.POST, instance=prefs)
    return HealthProfileForm(instance=prefs)
