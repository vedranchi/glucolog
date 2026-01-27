from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm

def register_view(request):
  if request.method == "POST":
    form = CustomUserCreationForm(request.POST)
    if form.is_valid():
      user = form.save()
      username = form.cleaned_data.get('username')
      login(request, user)
      messages.success(request, f"Account created for {username}")
      return redirect('glucolog-dashboard')
  else:
    form = CustomUserCreationForm()
  return render(request, 'users/register.html', {'form': form})

def login_view(request):
  if request.method == "POST":
    form = AuthenticationForm(request=request, data=request.POST)
    if form.is_valid(): 
      username = form.cleaned_data.get('username')
      password = form.cleaned_data.get('password')
      user = authenticate(email=username, password=password)
      if user is not None:
        login(request, user)
        messages.success(request, f"Welcome back, {user.username}!")
        return redirect('glucolog-dashboard')
    else: 
      messages.error(request, "Invalid username or password")
  else:
    form = AuthenticationForm()
  return render(request, 'users/login.html', {"form": form})

def user_profile_view(request):
    return render(request, 'users/profile.html')
  
    

def logout_view(request):
  logout(request)
  # redirect to login
  return redirect('glucolog-home')