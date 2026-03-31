from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q, Avg, Count
from django.db.models.functions import TruncDate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from logs.models import InsulinLog, GlucoseLog, MealLog
from users.models import UserPreferences
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation


@login_required
def log_insulin(request):
    """view for the log insulin page"""
    # filter todays logs
    today = timezone.now().date()
    insulin_today = InsulinLog.objects.filter(
        user=request.user, taken_at__date=today, is_deleted=False
    )
    basal_today = InsulinLog.objects.filter(
        user=request.user,
        insulin_type="basal",
        taken_at__date=today,
        is_deleted=False,
    )
    bolus_today = InsulinLog.objects.filter(
        user=request.user,
        insulin_type="bolus",
        taken_at__date=today,
        is_deleted=False,
    )

    # compute totals
    total_insulin = (
        round(sum(i.units for i in insulin_today), 1)
        if insulin_today.exists()
        else None
    )
    basal_units = round(sum(i.units for i in basal_today), 1)
    bolus_units = round(sum(i.units for i in bolus_today))

    # recent insulin activity
    recent_activity = []
    for i in insulin_today:
        recent_activity.append(
            {
                "id": i.id,
                "units": i.units,
                "type": i.insulin_type,
                "brand": i.brand,
                "note": i.note,
                "when": i.taken_at,
            }
        )

    # sort, get last 5 entries
    def get_time(activity):
        return activity["when"]

    recent_activity = sorted(recent_activity, key=get_time, reverse=True)[:5]

    # compute last 7 days doses
    last_seven_days = timezone.now() - timedelta(days=7)
    weekly_insulin = list(
        InsulinLog.objects.filter(
            user=request.user, taken_at__gte=last_seven_days, is_deleted=False
        )
        .annotate(date=TruncDate("taken_at"))  # only take the date
        .values("date")
        .annotate(
            basal_units=Sum(
                "units", filter=Q(insulin_type="basal")
            ),  # total basal units
            bolus_units=Sum(
                "units", filter=Q(insulin_type="bolus")
            ),  # total bolus units
        )
        .order_by("-date")
    )
    # separately highlight corrections
    correction_logs = list(
        InsulinLog.objects.filter(
            user=request.user,
            taken_at__gte=last_seven_days,
            note__iexact="correction",
            is_deleted=False,
        )
        .values("units", "insulin_type", "brand", "note", "taken_at")
        .order_by("-taken_at")
    )

    # pass variables to log_insulin
    context = {
        "total_units_today": total_insulin,
        "basal_today": basal_units,
        "bolus_today": bolus_units,
        "weekly_insulin": weekly_insulin,
        "weekly_corrections": correction_logs,
        "recent_insulin": recent_activity,
    }

    return render(request, "logs/log_insulin.html", context)


@login_required
def add_insulin(request, pk=None):
    # if pk exist edit, else create new record
    insulin = get_object_or_404(InsulinLog, user=request.user, pk=pk) if pk else None

    """log insulin dose"""
    if request.method == "POST":
        units = request.POST.get("units")
        insulin_type = request.POST.get("insulin_type")
        brand = request.POST.get("brand")
        note = request.POST.get("note")

        if insulin:
            # update existing record
            insulin.units = units
            insulin.insulin_type = insulin_type
            insulin.brand = brand
            insulin.note = note
            insulin.save()
        else:
            # create new record
            InsulinLog.objects.create(
                user=request.user,
                units=units,
                insulin_type=insulin_type,
                brand=brand,
                note=note,
            )
        return redirect("log-insulin")

    # render form
    context = {"insulin": insulin, "is_edit_mode": bool(insulin)}
    return render(request, "logs/add_insulin.html", context)


@login_required
@require_POST
def delete_insulin_record(request, pk):
    insulin = get_object_or_404(InsulinLog, pk=pk, user=request.user, is_deleted=False)
    insulin.is_deleted = True
    insulin.deleted_at = timezone.now()
    insulin.save()
    return redirect("log-insulin")


@login_required
def log_glucose(request):
    """log glucose page"""
    # get user preference
    profile, _ = UserPreferences.objects.get_or_create(user=request.user)
    unit = profile.glucose_unit
    unit_label = "mg/dL" if unit == "mg/dL" else "mmol/L"

    today = timezone.now().date()

    # current glucose
    current_glucose = (
        GlucoseLog.objects.filter(user=request.user, is_deleted=False)
        .order_by("-measured_at")
        .first()
    )

    # average glucose from number of readings
    glucose_stats = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    ).aggregate(
        avg_glucose=Avg("value"), count_glucose=Count("id"), total_glucose=Sum("value")
    )

    # convert if needed
    avg_glucose = glucose_stats["avg_glucose"]
    if avg_glucose and unit_label == "mg/dL":
        avg_glucose = round(avg_glucose * 18, 1)

    # last 10 readings ( time (hh:mm) and value )
    glucose_today = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    )

    recent_activity = []
    for g in glucose_today:
        value = float(g.value)
        if unit_label == "mg/dL":
            value = round(value * 18, 1)

        recent_activity.append(
            {
                "id": g.id,
                "value": g.value,
                "note": g.note,
                "context": g.context,
                "when": g.measured_at,
            }
        )

    # sort, get last 10 entries
    def get_time(activity):
        return activity["when"]

    recent_activity = sorted(recent_activity, key=get_time, reverse=True)[:10]

    # convert current glucose if needed
    current_value = None
    if current_glucose:
        current_value = float(current_glucose.value)
        if unit_label == "mg/dL":
            current_value = round(current_value * 18, 1)

    # compute last 7 days readings
    last_seven_days = timezone.now().date() - timedelta(days=6)
    # Get daily average glucose for the last 7 days (including today)
    weekly_glucose = list(
        GlucoseLog.objects.filter(
            user=request.user, measured_at__date__gte=last_seven_days, is_deleted=False
        )
        .annotate(date=TruncDate("measured_at"))
        .values("date")
        .annotate(
            avg_glucose=Avg("value"),
            count=Count("id"),
        )
        .order_by("-date")
    )

    seven_days_ago = timezone.now() - timedelta(days=7)

    recent_7_days = GlucoseLog.objects.filter(
        user=request.user, measured_at__gte=seven_days_ago, is_deleted=False
    ).order_by("-measured_at")

    # Convert avg_glucose to mg/dL if needed
    for entry in weekly_glucose:
        if entry["avg_glucose"] is not None and unit_label == "mg/dL":
            entry["avg_glucose"] = round(entry["avg_glucose"] * 18, 1)

    # pass variables to log_glucose
    context = {
        "current_glucose_value": current_value,
        "current_glucose_time": (
            current_glucose.measured_at if current_glucose else None
        ),
        "avg_glucose": avg_glucose,
        "total_glucose": glucose_stats["total_glucose"],
        "reading_count": glucose_stats["count_glucose"],
        "recent_activity": recent_activity,
        "unit_label": unit_label,
        "weekly_glucose": weekly_glucose,
        "recent_seven_days": recent_7_days,
    }

    return render(request, "logs/log_glucose.html", context)


@login_required
def add_glucose(request, pk=None):

    # if pk exist edit, else add new dose
    glucose = get_object_or_404(GlucoseLog, pk=pk, user=request.user) if pk else None

    # get user unit preference
    profile, _ = UserPreferences.objects.get_or_create(user=request.user)
    unit = profile.glucose_unit
    unit_label = "mg/dL" if unit == "mg/dL" else "mmol/L"

    error = None
    if request.method == "POST":
        raw_value = request.POST.get("value")
        note = request.POST.get("note") or ""
        context = request.POST.get("context") or ""

        try:
            value = Decimal(raw_value)
        except (TypeError, InvalidOperation):
            error = "Enter a valid number"
        else:
            if unit == "mmol":
                if value < Decimal("1") or value > Decimal("40"):
                    error = (
                        "Too high/low for mmol/L. Check if unit preference is correct"
                    )
                else:
                    mmol_value = value  # already mmol
            else:  # mg/dL
                if value < Decimal("20") or value > Decimal("700"):
                    error = (
                        "Too high/low for mg/dL. Check if unit preference is correct"
                    )
                else:
                    # convert mg/dL to mmol/L
                    mmol_value = (value / Decimal("18")).quantize(Decimal("0.1"))
        if not error:
            if glucose:
                glucose.value = mmol_value
                glucose.note = note
                glucose.context = context
                glucose.save()
            else:
                GlucoseLog.objects.create(
                    user=request.user,
                    value=mmol_value,
                    note=note,
                    context=context,
                )
            return redirect("log-glucose")

    return render(
        request,
        "logs/add_glucose.html",
        {
            "glucose": glucose,
            "is_edit_mode": bool(glucose),
            "unit_label": unit_label,
            "error": error,
        },
    )


@login_required
@require_POST
def delete_glucose_reading(request, pk):
    glucose = get_object_or_404(GlucoseLog, pk=pk, user=request.user, is_deleted=False)
    glucose.is_deleted = True
    glucose.deleted_at = timezone.now()
    glucose.save()
    return redirect("log-glucose")


@login_required
def log_meal(request):
    """log meals page"""
    today = timezone.now().date()

    totals = MealLog.objects.filter(
        user=request.user, eaten_at__date=today, is_deleted=False
    ).aggregate(
        carbs_today=Sum("carbs"),
        protein_today=Sum("protein"),
        fats_today=Sum("fats"),
        calories_today=Sum("calories"),
    )

    carbs_today = totals["carbs_today"] or 0
    protein_today = totals["protein_today"] or 0
    fats_today = totals["fats_today"] or 0
    calories_today = totals["calories_today"] or 0

    # last 5 meals
    recent_meals = MealLog.objects.filter(user=request.user, is_deleted=False).order_by(
        "-eaten_at"
    )[:5]

    # pass over the variables
    context = {
        "carbs_today": carbs_today,
        "protein_today": protein_today,
        "fats_today": fats_today,
        "calories_today": calories_today,
        "recent_meals": recent_meals,
    }
    return render(request, "logs/log_meal.html", context)


@login_required
def add_meal(request, pk=None):
    """add glucose reading"""
    meal = get_object_or_404(MealLog, pk=pk, user=request.user) if pk else None
    
    if request.method == "POST":
        carbs = request.POST.get("carbs")
        protein = request.POST.get("protein")
        fats = request.POST.get("fats")
        calories = request.POST.get("calories")
        note = request.POST.get("note")
        context = request.POST.get("context")
        
        if meal:
            meal.carbs = carbs
            meal.protein = protein
            meal.fats = fats
            meal.calories = calories
            meal.context = context
            meal.note = note
            meal.save()
        else:
            MealLog.objects.create(
                user=request.user,
                carbs=carbs,
                protein=protein,
                fats=fats,
                calories=calories,
                note=note,
                context=context,
            )
        return redirect("log-meal")

    context = {"meal": meal, "is_edit_mode": bool(meal)}
    return render(request, "logs/add_meal.html", context)


@login_required
@require_POST
def delete_meal_log(request, pk):
    meal = get_object_or_404(MealLog, user=request.user, pk=pk, is_deleted=False) 
    meal.is_deleted = True
    meal.deleted_at = timezone.now()
    meal.save()
    return redirect('log-meal')
    