# Glucolog Code Review

**Date:** 2026-03-30
**Scope:** Full codebase — bugs, security, design, and code quality

---

## Critical Bugs

### 1. IDOR Vulnerability — Any User Can Edit Another User's Insulin Log

**File:** `logs/views/logs.py`, line 109

```python
# BUG: no user= filter here
insulin = get_object_or_404(InsulinLog, pk=pk) if pk else None
```

The edit path for insulin logs does **not** scope by `user=request.user`. Any authenticated user can navigate to `/log/insulin/<pk>/edit/` and modify another user's record. Compare this to `add_glucose` and `add_meal`, which both correctly pass `user=request.user` to `get_object_or_404`. This should be:

```python
insulin = get_object_or_404(InsulinLog, pk=pk, user=request.user) if pk else None
```

---

### 2. Wrong Field Name on Insulin Edit — Updates Are Silently Lost

**File:** `logs/views/logs.py`, line 123

```python
insulin.type = insulin_type   # BUG — model field is insulin_type, not type
```

`InsulinLog` has no attribute called `type`. Django silently sets a Python attribute on the object instance, but it never reaches the database column. When a user edits an insulin log's type (basal/bolus), the change is dropped. It should be:

```python
insulin.insulin_type = insulin_type
```

---

### 3. Dashboard Does Not Filter Soft-Deleted Records

**File:** `dashboard/views.py`, lines 20–24

```python
glucose_today = GlucoseLog.objects.filter(user=request.user, measured_at__date=today)
insulin_today = InsulinLog.objects.filter(user=request.user, taken_at__date=today)
meals_today = MealLog.objects.filter(user=request.user, eaten_at__date=today)
```

All three querysets are missing `is_deleted=False`. Deleted records appear in the dashboard's summary stats (average glucose, total insulin, carbs) and in the recent activity feed, and they can have their edit URLs surfaced to the user. Every log query in `logs/views/logs.py` correctly applies this filter; the dashboard is the exception.

---

### 4. Glucose Unit Conversion Computed But Discarded in Recent Activity

**File:** `logs/views/logs.py`, lines 186–199

```python
for g in glucose_today:
    value = float(g.value)
    if unit_label == "mg/dL":
        value = round(value * 18, 1)   # converted value, never used

    recent_activity.append({
        "id": g.id,
        "value": g.value,              # BUG: raw mmol/L value always shown
        ...
    })
```

The converted `value` variable is computed and then immediately thrown away. The dict stores `g.value` (always mmol/L). Users with mg/dL preference see the wrong unit in recent activity on the glucose log page.

---

### 5. `carbs_consumed` on Dashboard Will Crash When Any Meal Has `carbs=None`

**File:** `dashboard/views.py`, line 51

```python
carbs_consumed = (
    round(sum(m.carbs for m in meals_today), 1) if meals_today.exists() else None
)
```

`MealLog.carbs` is nullable (`null=True, blank=True`). If any meal today has no carbs entered, iterating `m.carbs` yields `None`, and `sum()` over mixed `Decimal`/`None` values raises a `TypeError`. Use `.aggregate(Sum("carbs"))` or explicitly filter out `None` values.

---

## Moderate Bugs

### 6. Bolus Units Rounded to Integer (Missing Decimal Argument)

**File:** `logs/views/logs.py`, line 42

```python
basal_units = round(sum(i.units for i in basal_today), 1)  # correct — 1 decimal
bolus_units = round(sum(i.units for i in bolus_today))      # BUG — rounds to int
```

`round()` with no `ndigits` argument returns an integer. Half-unit bolus doses (common in insulin therapy) are silently rounded. Should be `round(..., 1)`.

---

### 7. No Input Validation on Insulin and Meal Forms

**Files:** `logs/views/logs.py` — `add_insulin` (line 113), `add_meal` (line 373)

Both views pass raw POST strings directly to model fields and `objects.create()`, with no `try/except` or validation:

```python
units = request.POST.get("units")   # could be "", "abc", or None
InsulinLog.objects.create(user=request.user, units=units, ...)
```

An empty or non-numeric value will raise an unhandled exception at the database layer, resulting in a 500 error. `add_glucose` handles this correctly with `Decimal()` conversion and an explicit `try/except`. The same pattern should be applied to `add_insulin` and `add_meal`.

---

### 8. `add_meal` Passes Empty String to Nullable Decimal Fields

Related to the above: if the user leaves optional fields (protein, fats, calories) blank, `request.POST.get()` returns `""`. Passing `""` to a `DecimalField` raises a `ValidationError` at the database level. These should be converted to `None` when blank.

---

## Design & Flow Issues

### 9. Profile Page — All Three Forms Submit on Every POST

**File:** `users/views.py` + `users/services.py`

```python
profile_form, update_prof = handle_profile_form(request)
preferences_form, update_pref = handle_preferences_form(request)
health_profile_form, update_health = handle_health_profile_form(request)
```

On every POST (regardless of which form the user submitted), all three handlers run, all three forms are bound with POST data, and all three are validated. Submitting the preferences form also validates the profile form and health form. Because all three forms are on the same page, their field names don't overlap right now, so it mostly works — but it's fragile. Adding a field that exists in two forms, or adding a required field to one, will cause silent cross-contamination. The standard pattern is to include a hidden `form_name` field and dispatch in the view, or split the forms into separate URL endpoints.

---

### 10. Glucose Edit Does Not Pre-Convert Value to User's Preferred Unit

**File:** `logs/views/logs.py` — `add_glucose`

Values are stored internally in mmol/L. When a user opens the edit form for a reading, the pre-filled value is the raw mmol/L — even if they originally entered it in mg/dL. A user who enters 180 mg/dL, saves, then edits will see 10.0 (mmol/L) pre-filled in a form labeled "mg/dL". The edit view needs to convert the stored value back to the display unit before rendering.

---

### 11. `logs/views/dashboard.py` — Dead Code With Active Bugs

**File:** `logs/views/dashboard.py`

This file contains three views (`insulin_dashboard`, `glucose_dashboard`, `meal_dashboard`) that are not wired to any URL and appear to be an old iteration. They contain several bugs:

- `MealLog.objects.create(..., desc=desc, ...)` — the `desc` field was removed in a migration; this would crash with an unexpected keyword argument.
- `InsulinLog.objects.create(user=request.user, units=units)` — `insulin_type` is required with no default; this would fail a DB constraint.
- No validation on any input.

The file should be deleted to avoid confusion.

---

### 12. `GlucoseLog.__str__` Hardcodes "mmol/L"

**File:** `logs/models.py`, line 41

```python
def __str__(self):
    return f"{self.user} - {self.value} mmol/L @ {self.measured_at}"
```

The label is always "mmol/L" regardless of the user's unit preference. While this is mainly a cosmetic issue in the admin panel, it's confusing for mg/dL users.

---

## Code Quality & Anti-Patterns

### 13. `logs/models.py` Imports Directly From `core.settings`

**File:** `logs/models.py`, line 2

```python
from core.settings import AUTH_USER_MODEL
```

Django models should always use `from django.conf import settings` and then reference `settings.AUTH_USER_MODEL`. Importing directly from the settings module bypasses Django's settings-override machinery (used in testing and multi-settings setups) and creates a tight coupling to the project's directory structure.

---

### 14. `CustomUserCreationForm.__init__` Calls Wrong `super()`

**File:** `users/forms.py`, line 12

```python
def __init__(self, *args, **kwargs):
    super(AdminUserCreationForm, self).__init__(*args, **kwargs)  # wrong
```

This passes `AdminUserCreationForm` as the first argument to `super()`, which means Python looks for the *parent* of `AdminUserCreationForm` in the MRO — effectively skipping `AdminUserCreationForm.__init__`. It works by coincidence because the field setup happens to be compatible, but it's a latent MRO bug. Should be `super().__init__(*args, **kwargs)`.

---

### 15. `recent_seven_days` Queryset Is Fetched but Unused in `log_glucose`

**File:** `logs/views/logs.py`, lines 230–234

```python
seven_days_ago = timezone.now() - timedelta(days=7)

recent_7_days = GlucoseLog.objects.filter(
    user=request.user, measured_at__gte=seven_days_ago, is_deleted=False
).order_by("-measured_at")
```

This overlaps significantly with `weekly_glucose` (computed just above it) and uses a slightly different time boundary (`timezone.now() - 7 days` vs `timezone.now().date() - 6 days`). Both hit the database. Check whether both are needed in the template or if one can be consolidated.

---

### 16. Inefficient Python-Side Aggregation in Dashboard

**File:** `dashboard/views.py`, lines 37–53

```python
avg_glucose = (
    round(sum(g.value for g in glucose_today) / glucose_today.count(), 1)
    if glucose_today.exists()
    else None
)
```

This fetches all glucose records into Python memory to compute the average, despite the DB being perfectly capable of doing it. This also calls `.count()` which is a second query, after `.exists()` which is a third. Use `.aggregate(Avg("value"), Count("id"))` as already done in `log_glucose`. The same applies to `total_insulin` and `carbs_consumed`.

---

### 17. Logout Accepts GET Requests

**File:** `users/views.py`, line 73

```python
def logout_view(request):
    logout(request)
    return redirect("glucolog-home")
```

Logout via GET is a CSRF risk: a malicious link (in an email, image tag, etc.) can silently log a user out. Django's own `LogoutView` now requires POST by default. Consider adding `@require_POST` to this view and updating the logout link in the templates to be a form.

---

### 18. Media Files Have No Production Serving Strategy

**File:** `core/urls.py`, line 15

```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

User-uploaded media (profile pictures) is only served by Django in development. In production, there is no configured mechanism (nginx, S3/Cloudfront, Whitenoise for media, etc.) to serve `MEDIA_ROOT`. Profile images will return 404s in production.

---

## Summary Table

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | 🔴 Critical | `logs/views/logs.py` | IDOR on insulin edit — missing `user=` filter |
| 2 | 🔴 Critical | `logs/views/logs.py` | `insulin.type` typo — edits never saved to DB |
| 3 | 🔴 Critical | `dashboard/views.py` | Soft-deleted records not filtered from dashboard |
| 4 | 🟠 High | `logs/views/logs.py` | mg/dL conversion computed but discarded in recent activity |
| 5 | 🟠 High | `dashboard/views.py` | `carbs_consumed` crashes on nullable carbs |
| 6 | 🟡 Moderate | `logs/views/logs.py` | `bolus_units` rounded to int (missing decimal arg) |
| 7 | 🟡 Moderate | `logs/views/logs.py` | No input validation on insulin/meal forms → 500 errors |
| 8 | 🟡 Moderate | `logs/views/logs.py` | Empty string passed to nullable Decimal fields |
| 9 | 🟡 Moderate | `users/views.py` | All 3 profile forms validated on every POST |
| 10 | 🟡 Moderate | `logs/views/logs.py` | Glucose edit doesn't pre-convert value to user's unit |
| 11 | 🟡 Moderate | `logs/views/dashboard.py` | Dead file with broken model references |
| 12 | 🔵 Low | `logs/models.py` | `__str__` hardcodes "mmol/L" unit |
| 13 | 🔵 Low | `logs/models.py` | Direct import from `core.settings` |
| 14 | 🔵 Low | `users/forms.py` | Wrong `super()` call in `CustomUserCreationForm` |
| 15 | 🔵 Low | `logs/views/logs.py` | Redundant/overlapping 7-day queryset |
| 16 | 🔵 Low | `dashboard/views.py` | Python-side aggregation instead of DB-level |
| 17 | 🔵 Low | `users/views.py` | Logout accessible via GET (CSRF risk) |
| 18 | 🔵 Low | `core/urls.py` | No production media serving strategy |
