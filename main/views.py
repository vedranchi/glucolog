from django.shortcuts import render, redirect
from django.contrib import messages

def home(request):
  if request.user.is_authenticated:
    return redirect("glucolog-dashboard")
  
  return render(request, "main/base.html")