from django.shortcuts import render, redirect
from logs.models import InsulinLog, GlucoseLog, MealLog
from django.contrib.auth.decorators import login_required

@login_required
def insulin_dashboard(request):
    """view for the insulin actions in the dashboard"""
    if request.method == "POST":
        units = request.POST.get("units")
        InsulinLog.objects.create(user=request.user, units=units)
        return redirect("glucolog-dashboard")

    return render(request, "logs/log_insulin.html")

@login_required
def glucose_dashboard(request):
    """view for the glucose actions in the dashboard"""
    if request.method == "POST":
        value = request.POST.get("value")
        GlucoseLog.objects.create(user=request.user, value=value)
        return redirect("glucolog-dashboard")

    return render(request, "logs/log_glucose.html")

@login_required
def meal_dashboard(request):
    """view for the meal actions in the dashboard"""
    if request.method == "POST":
        carbs = request.POST.get("carbs")
        desc = request.POST.get("desc")
        MealLog.objects.create(user=request.user, desc=desc, carbs=carbs)
        return redirect("glucolog-dashboard")

    return render(request, "logs/log_meal.html")