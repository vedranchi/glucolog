from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required

from .services import (
    handle_preferences_form,
    handle_health_profile_form,
    handle_profile_form,
)
from .forms import CustomUserCreationForm


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get("username")
            login(request, user)
            messages.success(request, f"Account created for {username}")
            return redirect("glucolog-dashboard")
    else:
        form = CustomUserCreationForm()
    return render(request, "users/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request=request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("glucolog-dashboard")
        else:
            messages.error(request, "Invalid username or password")
    else:
        form = AuthenticationForm()
    return render(request, "users/login.html", {"form": form})


@login_required
def user_profile_view(request):
    profile_form, update_prof = handle_profile_form(request)
    preferences_form, update_pref = handle_preferences_form(request)
    health_profile_form, update_health = handle_health_profile_form(request)

    if update_prof:
        messages.success(request, "Profile updated")
        return redirect("user-profile")

    if update_pref:
        messages.success(request, "Preferences updated")
        return redirect("user-profile")

    if update_health:
        messages.success(request, "Health profile updated")
        return redirect("user-profile")

    context = {
        "preferences_form": preferences_form,
        "health_profile_form": health_profile_form,
        "update_profile_form": profile_form
    }
    return render(request, "users/profile.html", context)


def logout_view(request):
    logout(request)
    # redirect to login
    return redirect("glucolog-home")
