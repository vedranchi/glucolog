from django.shortcuts import render, redirect

def home(request):
  if request.user.is_authenticated:
    return redirect("glucoread-dashboard")
  
  return render(request, "landing/index.html")
