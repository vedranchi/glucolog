from django.shortcuts import render
from django.db.models import Avg, Count, Sum
from logs.models import GlucoseLog, InsulinLog, MealLog
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from datetime import datetime, timedelta

from users.models import UserPreferences
from users.services import get_user_preferences
from logs.conversions import to_display


@login_required
def dashboard(request):
    profile = get_user_preferences(request.user)
    is_mgdl = profile.glucose_unit == UserPreferences.GLUCOSE_UNIT_MGDL
    unit_label = "mg/dL" if is_mgdl else "mmol/L"

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

    latest_glucose_value = to_display(
        latest_glucose.value if latest_glucose else None, is_mgdl
    )

    glucose_stats = glucose_today.aggregate(avg_glucose=Avg("value"), count=Count("id"))
    avg_glucose = to_display(glucose_stats["avg_glucose"], is_mgdl)

    insulin_stats = insulin_today.aggregate(total_units=Sum("units"), count=Count("id"))
    total_insulin = (
        round(insulin_stats["total_units"], 1) if insulin_stats["count"] else None
    )

    # SUM ignores NULLs, matching the previous `m.carbs or 0` per-row fallback
    meal_stats = meals_today.aggregate(total_carbs=Sum("carbs"), count=Count("id"))
    carbs_consumed = (
        round(meal_stats["total_carbs"] or 0, 1) if meal_stats["count"] else None
    )

    # build recent activity feed from all three log types, show last 5
    recent_activity = []
    for g in glucose_today:
        recent_activity.append(
            {
                "label": f"Glucose reading ({to_display(g.value, is_mgdl)} {unit_label})",
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
                # note is nullable, and the seeder creates meals without one —
                # an f-string would render the literal text "Meal (None)".
                "label": f"Meal ({m.note})" if m.note else "Meal",
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

    # explicit ordering — the chart draws points in list order, so an
    # unordered queryset would zigzag the line
    glucose_chart_day = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=chart_date, is_deleted=False
    ).order_by("measured_at")

    glucose_labels = [g.measured_at.strftime("%H:%M") for g in glucose_chart_day]
    glucose_values = [to_display(g.value, is_mgdl) for g in glucose_chart_day]

    previous_chart_date = chart_date - timedelta(days=1)
    next_chart_date = chart_date + timedelta(days=1)
    if next_chart_date > today:
        next_chart_date = None

    context = {
        "avg_glucose": avg_glucose,
        "total_insulin": total_insulin,
        "carbs_consumed": carbs_consumed,
        "recent_activity": recent_activity,
        "glucose_count_today": glucose_stats["count"],
        "insulin_count_today": insulin_stats["count"],
        "meal_count_today": meal_stats["count"],
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
