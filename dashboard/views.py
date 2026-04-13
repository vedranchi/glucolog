from django.shortcuts import render
from logs.models import GlucoseLog, InsulinLog, MealLog
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from datetime import datetime, timedelta

from users.services import get_user_preferences

# standard conversion factor between mmol/L and mg/dL
MMOL_TO_MGDL = 18


@login_required
def dashboard(request):
    profile = get_user_preferences(request.user)
    unit = profile.glucose_unit
    unit_label = "mg/dL" if unit == "mg/dL" else "mmol/L"

    today = timezone.now().date()

    glucose_today = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    )
    insulin_today = InsulinLog.objects.filter(
        user=request.user, taken_at__date=today, is_deleted=False
    )
    meals_today = MealLog.objects.filter(
        user=request.user, eaten_at__date=today, is_deleted=False
    )

    latest_glucose = glucose_today.order_by("-measured_at").first()
    latest_insulin = insulin_today.order_by("-taken_at").first()
    latest_meal = meals_today.order_by("-eaten_at").first()

    latest_glucose_value = None
    if latest_glucose:
        latest_glucose_value = float(latest_glucose.value)
        if unit_label == "mg/dL":
            latest_glucose_value *= MMOL_TO_MGDL
        latest_glucose_value = round(latest_glucose_value, 1)

    avg_glucose = (
        round(sum(g.value for g in glucose_today) / glucose_today.count(), 1)
        if glucose_today.exists()
        else None
    )
    if unit_label == "mg/dL" and avg_glucose is not None:
        avg_glucose = round(avg_glucose * MMOL_TO_MGDL, 1)

    total_insulin = (
        round(sum(i.units for i in insulin_today), 1)
        if insulin_today.exists()
        else None
    )

    # carbs uses `or 0` because MealLog.carbs is nullable
    carbs_consumed = (
        round(sum(m.carbs or 0 for m in meals_today), 1)
        if meals_today.exists()
        else None
    )

    # build recent activity feed from all three log types, show last 5
    recent_activity = []
    for g in glucose_today:
        value = float(g.value)
        if unit_label == "mg/dL":
            value = round(value * MMOL_TO_MGDL, 1)
        recent_activity.append(
            {
                "label": f"Glucose reading ({value} {unit_label})",
                "when": g.measured_at,
                "edit_url": reverse("edit-glucose", kwargs={"pk": g.id}),
            }
        )
    for i in insulin_today:
        recent_activity.append(
            {
                "label": f"Insulin dose ({i.units} U)",
                "when": i.taken_at,
                "edit_url": reverse("edit-insulin", kwargs={"pk": i.id}),
            }
        )
    for m in meals_today:
        recent_activity.append(
            {
                "label": f"Meal ({m.note})",
                "when": m.eaten_at,
                "edit_url": reverse("edit-meal", kwargs={"pk": m.id}),
            }
        )
    recent_activity = sorted(recent_activity, key=lambda a: a["when"], reverse=True)[:5]

    # chart date navigation — defaults to today, clamped so next never exceeds today
    chart_date_param = request.GET.get("chart_date")
    chart_date = today
    if chart_date_param:
        try:
            chart_date = datetime.strptime(chart_date_param, "%Y-%m-%d").date()
        except ValueError:
            chart_date = today

    glucose_chart_day = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=chart_date, is_deleted=False
    )

    glucose_labels = [g.measured_at.strftime("%H:%M") for g in glucose_chart_day]
    glucose_values = []
    for g in glucose_chart_day:
        value = float(g.value)
        if unit_label == "mg/dL":
            value = value * MMOL_TO_MGDL
        glucose_values.append(round(value, 1))

    previous_chart_date = chart_date - timedelta(days=1)
    next_chart_date = chart_date + timedelta(days=1)
    if next_chart_date > today:
        next_chart_date = None

    context = {
        "avg_glucose": avg_glucose,
        "total_insulin": total_insulin,
        "carbs_consumed": carbs_consumed,
        "recent_activity": recent_activity,
        "glucose_count_today": glucose_today.count(),
        "insulin_count_today": insulin_today.count(),
        "meal_count_today": meals_today.count(),
        "latest_glucose": latest_glucose,
        "latest_glucose_value": latest_glucose_value,
        "latest_insulin": latest_insulin,
        "latest_meal": latest_meal,
        "chart_date": chart_date,
        "previous_chart_date": previous_chart_date,
        "next_chart_date": next_chart_date,
        "glucose_labels": glucose_labels,
        "glucose_values": glucose_values,
        "unit_label": unit_label,
    }

    return render(request, "dashboard/dashboard.html", context)
