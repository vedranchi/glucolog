from django.shortcuts import render
from logs.models import GlucoseLog, InsulinLog, MealLog
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import json

from users.services import get_user_preferences

@login_required
def dashboard(request):
    # get user unit preference
    profile = get_user_preferences(request.user)
    unit = profile.glucose_unit
    unit_label = "mg/dL" if unit == "mg/dL" else "mmol/L"

    # filter todays logs
    today = timezone.now().date()
    glucose_today = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today
    )
    insulin_today = InsulinLog.objects.filter(user=request.user, taken_at__date=today)
    meals_today = MealLog.objects.filter(user=request.user, eaten_at__date=today)

    # compute summary
    avg_glucose = (
        round(sum(g.value for g in glucose_today) / glucose_today.count(), 1)
        if glucose_today.exists()
        else None
    )
    if unit_label == 'mg/dL' and glucose_today.exists():
        avg_glucose = round(avg_glucose * 18, 1)
        
    total_insulin = (
        round(sum(i.units for i in insulin_today), 1)
        if insulin_today.exists()
        else None
    )
    carbs_consumed = (
        round(sum(m.carbs for m in meals_today), 1) if meals_today.exists() else None
    )

    # build recent activity ( last 5 entries )
    recent_activity = []
    for g in glucose_today:
        recent_activity.append(
            {"label": f"Glucose reading ({g.value})", "when": g.measured_at}
        )
    for i in insulin_today:
        recent_activity.append(
            {"label": f"Insulin dose ({i.units} U)", "when": i.taken_at}
        )
    for m in meals_today:
        recent_activity.append({"label": f"Meal ({m.note})", "when": m.eaten_at})

    # sort, get last 5 entries
    def get_time(activity):
        return activity["when"]

    recent_activity = sorted(recent_activity, key=get_time, reverse=True)[:5]

    # get data for the chart
    glucose_labels = [g.measured_at.strftime("%H:%M") for g in glucose_today]
    glucose_values = []
    for g in glucose_today:
        value = float(g.value)
        if unit_label == 'mg/dL':
            value = value * 18 # convert to mg/dL
        glucose_values.append(round(value, 1))

    # send data to dashboard.html
    context = {
        "avg_glucose": avg_glucose,
        "total_insulin": total_insulin,
        "carbs_consumed": carbs_consumed,
        "recent_activity": recent_activity,
        # for chart
        "glucose_labels": json.dumps(glucose_labels),
        "glucose_values": json.dumps(glucose_values),
        "unit_label": unit_label,
    }

    return render(request, "dashboard/dashboard.html", context)

