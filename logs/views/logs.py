from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Q, Avg, Count
from django.db.models.functions import TruncDate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from logs.models import InsulinLog, GlucoseLog, MealLog
from users.models import UserPreferences
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from logs.conversions import MMOL_TO_MGDL, mgdl_to_mmol


@login_required
def log_insulin(request):
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

    total_insulin = (
        round(sum(i.units for i in insulin_today), 1)
        if insulin_today.exists()
        else None
    )
    basal_units = round(sum(i.units for i in basal_today), 1)
    bolus_units = round(sum(i.units for i in bolus_today), 1)

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
    recent_activity = sorted(recent_activity, key=lambda a: a["when"], reverse=True)[:5]

    last_seven_days = timezone.now() - timedelta(days=7)

    # daily basal/bolus totals for the weekly chart
    weekly_insulin = list(
        InsulinLog.objects.filter(
            user=request.user, taken_at__gte=last_seven_days, is_deleted=False
        )
        .annotate(date=TruncDate("taken_at"))
        .values("date")
        .annotate(
            basal_units=Sum("units", filter=Q(insulin_type="basal")),
            bolus_units=Sum("units", filter=Q(insulin_type="bolus")),
        )
        .order_by("-date")
    )

    # doses the user marked as corrections (note="correction", case-insensitive)
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
    """Add a new insulin dose or edit an existing one when pk is provided."""
    insulin = (
        get_object_or_404(InsulinLog, user=request.user, is_deleted=False, pk=pk)
        if pk
        else None
    )

    if request.method == "POST":
        try:
            units = Decimal(request.POST.get("units"))
            if units <= 0 or units >= 300:
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Invalid units value.")
            # stay in edit mode when editing, otherwise back to the add form
            if insulin:
                return redirect("edit-insulin", pk=insulin.pk)
            return redirect("add-insulin")

        insulin_type = request.POST.get("insulin_type")
        if insulin_type not in dict(InsulinLog.INSULIN_TYPES):
            messages.error(request, "Invalid insulin type.")
            if insulin:
                return redirect("edit-insulin", pk=insulin.pk)
            return redirect("add-insulin")

        brand = request.POST.get("brand")
        note = request.POST.get("note")

        if insulin:
            insulin.units = units
            insulin.insulin_type = insulin_type
            insulin.brand = brand
            insulin.note = note
            insulin.save()
        else:
            InsulinLog.objects.create(
                user=request.user,
                units=units,
                insulin_type=insulin_type,
                brand=brand,
                note=note,
            )
        return redirect("log-insulin")

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
    profile, _ = UserPreferences.objects.get_or_create(user=request.user)
    unit = profile.glucose_unit
    unit_label = "mg/dL" if unit == "mg/dL" else "mmol/L"

    today = timezone.now().date()

    # most recent reading across all time, not just today
    current_glucose = (
        GlucoseLog.objects.filter(user=request.user, is_deleted=False)
        .order_by("-measured_at")
        .first()
    )

    glucose_stats = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    ).aggregate(
        avg_glucose=Avg("value"), count_glucose=Count("id"), total_glucose=Sum("value")
    )

    avg_glucose = glucose_stats["avg_glucose"]
    if avg_glucose and unit_label == "mg/dL":
        avg_glucose = round(avg_glucose * MMOL_TO_MGDL, 1)

    glucose_today = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    )

    # today's readings list, converted to display unit
    recent_activity = []
    for g in glucose_today:
        value = float(g.value)
        if unit_label == "mg/dL":
            value = round(value * MMOL_TO_MGDL, 1)
        recent_activity.append(
            {
                "id": g.id,
                "value": value,
                "note": g.note,
                "context": g.context,
                "when": g.measured_at,
            }
        )
    recent_activity = sorted(recent_activity, key=lambda a: a["when"], reverse=True)[:10]

    current_value = None
    if current_glucose:
        current_value = float(current_glucose.value)
        if unit_label == "mg/dL":
            current_value = round(current_value * MMOL_TO_MGDL, 1)

    # daily averages for the weekly summary table
    last_seven_days = timezone.now().date() - timedelta(days=6)
    weekly_glucose = list(
        GlucoseLog.objects.filter(
            user=request.user, measured_at__date__gte=last_seven_days, is_deleted=False
        )
        .annotate(date=TruncDate("measured_at"))
        .values("date")
        .annotate(avg_glucose=Avg("value"), count=Count("id"))
        .order_by("-date")
    )

    # individual readings for the 7-day detail list (rolling window, not calendar days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_7_days_qs = GlucoseLog.objects.filter(
        user=request.user, measured_at__gte=seven_days_ago, is_deleted=False
    ).order_by("-measured_at")

    recent_7_days = []
    for g in recent_7_days_qs:
        value = float(g.value)
        if unit_label == "mg/dL":
            value = round(value * MMOL_TO_MGDL, 1)
        recent_7_days.append(
            {
                "value": value,
                "measured_at": g.measured_at,
                "context": g.context,
                "note": g.note,
                "id": g.id,
            }
        )

    for entry in weekly_glucose:
        if entry["avg_glucose"] is not None and unit_label == "mg/dL":
            entry["avg_glucose"] = round(entry["avg_glucose"] * MMOL_TO_MGDL, 1)

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
    """Add a new glucose reading or edit an existing one when pk is provided."""
    glucose = (
        get_object_or_404(GlucoseLog, pk=pk, is_deleted=False, user=request.user)
        if pk
        else None
    )

    profile, _ = UserPreferences.objects.get_or_create(user=request.user)
    unit = profile.glucose_unit
    unit_label = "mg/dL" if unit == "mg/dL" else "mmol/L"

    error = None
    if request.method == "POST":
        raw_value = request.POST.get("value")
        note = request.POST.get("note") or ""
        # empty selection falls back to the model default; anything else must be a real choice
        context = request.POST.get("context") or "other"

        if context not in dict(GlucoseLog.CONTEXT):
            error = "Invalid reading context."

        try:
            value = Decimal(raw_value)
        except (TypeError, InvalidOperation):
            error = "Enter a valid number"
        else:
            # NaN and Infinity construct without raising, so they reach here;
            # the range comparisons below would then raise InvalidOperation
            # outside the try above and surface as a 500.
            if not value.is_finite():
                error = "Enter a valid number"
            elif unit == "mmol":
                if value < Decimal("1") or value > Decimal("40"):
                    error = "Too high/low for mmol/L. Check if unit preference is correct"
                else:
                    mmol_value = value
            else:  # mg/dL — convert to mmol/L before storing
                if value < Decimal("20") or value > Decimal("700"):
                    error = "Too high/low for mg/dL. Check if unit preference is correct"
                else:
                    mmol_value = mgdl_to_mmol(value)

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

    # convert stored mmol/L back to the user's display unit for pre-filling the edit form
    prefill_value = None
    if glucose:
        prefill_value = float(glucose.value)
        if unit == "mg/dL":
            prefill_value = round(prefill_value * MMOL_TO_MGDL, 1)
        else:
            prefill_value = round(prefill_value, 1)

    return render(
        request,
        "logs/add_glucose.html",
        {
            "glucose": glucose,
            "is_edit_mode": bool(glucose),
            "unit_label": unit_label,
            "error": error,
            "prefill_value": prefill_value,
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
    today = timezone.now().date()

    totals = MealLog.objects.filter(
        user=request.user, eaten_at__date=today, is_deleted=False
    ).aggregate(
        carbs_today=Sum("carbs"),
        protein_today=Sum("protein"),
        fats_today=Sum("fats"),
        calories_today=Sum("calories"),
    )

    # aggregate returns None when no rows match; default to 0 for display
    carbs_today = totals["carbs_today"] or 0
    protein_today = totals["protein_today"] or 0
    fats_today = totals["fats_today"] or 0
    calories_today = totals["calories_today"] or 0

    recent_meals = MealLog.objects.filter(user=request.user, is_deleted=False).order_by(
        "-eaten_at"
    )[:5]

    context = {
        "carbs_today": carbs_today,
        "protein_today": protein_today,
        "fats_today": fats_today,
        "calories_today": calories_today,
        "recent_meals": recent_meals,
    }
    return render(request, "logs/log_meal.html", context)


def parse_macro(value):
    """Convert a POST string to a Decimal nutrition amount.

    Blank means "not provided" and maps to None (the fields are nullable).
    Garbage, negative, or out-of-range input raises ValueError so the view
    can reject the submission instead of silently dropping data.
    """
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError("not a number")
    # NaN and Infinity construct without raising, but every comparison against
    # them raises InvalidOperation — and Postgres numeric accepts NaN, so one
    # stored value would poison this user's Sum() totals permanently. Reject
    # them before the range check below can touch them.
    if not parsed.is_finite():
        raise ValueError("not a number")
    # nutrition can't be negative; the model fields cap out at 9999.9
    if parsed < 0 or parsed >= Decimal("10000"):
        raise ValueError("out of range")
    return parsed


@login_required
def add_meal(request, pk=None):
    """Add a new meal log or edit an existing one when pk is provided."""
    meal = (
        get_object_or_404(MealLog, pk=pk, is_deleted=False, user=request.user)
        if pk
        else None
    )

    if request.method == "POST":
        try:
            carbs = parse_macro(request.POST.get("carbs"))
            protein = parse_macro(request.POST.get("protein"))
            fats = parse_macro(request.POST.get("fats"))
            calories = parse_macro(request.POST.get("calories"))
        except ValueError:
            messages.error(request, "Nutrition values must be numbers between 0 and 9999.9.")
            if meal:
                return redirect("edit-meal", pk=meal.pk)
            return redirect("add-meal")

        note = request.POST.get("note")
        # empty selection falls back to the model default; anything else must be a real choice
        context = request.POST.get("context") or "breakfast"
        if context not in dict(MealLog.CONTEXT):
            messages.error(request, "Invalid meal type.")
            if meal:
                return redirect("edit-meal", pk=meal.pk)
            return redirect("add-meal")

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
    return redirect("log-meal")
