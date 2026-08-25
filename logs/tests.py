from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.urls import reverse
from logs.models import GlucoseLog, InsulinLog, MealLog
from users.models import UserPreferences
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


# test the glucose log model
class GlucoseLogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test", password="tester123")

    def test_glucose_log_creation(self):
        log = GlucoseLog.objects.create(
            user=self.user, value=6.0, measured_at="2025-01-01T20:00:00Z"
        )
        # test user and value data
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.value, 6.0)

    def test_string_representation_contains_no_health_data(self):
        """__str__ is captured by tracebacks, error reporters and admin logs.

        This test previously asserted the opposite — that the reading appeared
        in __str__ — which is exactly the behaviour that would have shipped a
        patient's glucose value to any third-party error reporter.
        """
        log = GlucoseLog.objects.create(
            user=self.user, value=Decimal("5.8"), measured_at="2025-01-01T21:00:00Z"
        )
        rendered = str(log)
        self.assertNotIn("5.8", rendered)
        self.assertNotIn(self.user.username, rendered)
        self.assertNotIn("2025-01-01", rendered)
        # still identifies the row well enough to look it up on purpose
        self.assertEqual(rendered, f"GlucoseLog #{log.pk}")

    def test_all_log_models_keep_measurements_out_of_str(self):
        insulin = InsulinLog.objects.create(
            user=self.user, units=Decimal("8.5"), insulin_type="bolus"
        )
        meal = MealLog.objects.create(
            user=self.user, carbs=Decimal("42.0"), context="lunch"
        )
        self.assertEqual(str(insulin), f"InsulinLog #{insulin.pk}")
        self.assertNotIn("8.5", str(insulin))
        self.assertEqual(str(meal), f"MealLog #{meal.pk}")
        self.assertNotIn("lunch", str(meal))


class GlucoseQueryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("test", "test123")
        self.client.login(username="test", password="test123")

        GlucoseLog.objects.create(user=self.user, value=5.2, measured_at=timezone.now())

        GlucoseLog.objects.create(
            user=self.user, value=6.8, measured_at=timezone.now() - timedelta(days=10)
        )

        # test only the last 7 days. Exclude the 10 day old query

    def test_last_7_days(self):
        seven_days_ago = timezone.now() - timedelta(days=7)

        qs = GlucoseLog.objects.filter(user=self.user, measured_at__gte=seven_days_ago)
        self.assertEqual(qs.count(), 1)  # expect one glucose reading to be returned


# unit conversion
class UnitConversionTest(TestCase):
    """Exercises the real conversion path through the views.

    The previous version of this test multiplied two numbers together inside
    its own assertion and imported nothing from the application, so it would
    have passed with every conversion in the codebase deleted.

    Glucose is stored canonically in mmol/L; mg/dL exists only at the edges.
    A bug here shows the user a reading that is wrong by a factor of 18, which
    is the most dangerous class of error this app can produce.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="mgdl", email="mgdl@example.com", password="pw12345!"
        )
        prefs = self.user.preferences
        prefs.glucose_unit = UserPreferences.GLUCOSE_UNIT_MGDL
        prefs.save()
        self.client.login(email="mgdl@example.com", password="pw12345!")

    def test_mgdl_input_is_stored_as_mmol(self):
        self.client.post(
            reverse("add-glucose"), {"value": "100", "context": "fasting"}
        )
        log = GlucoseLog.objects.get(user=self.user)
        # 100 / 18 = 5.5555... quantised to two decimal places
        self.assertEqual(log.value, Decimal("5.56"))

    def test_mgdl_user_sees_mgdl_on_the_log_page(self):
        GlucoseLog.objects.create(user=self.user, value=Decimal("5.56"))
        response = self.client.get(reverse("log-glucose"))
        self.assertEqual(response.context["unit_label"], "mg/dL")
        # 5.56 * 18 — the documented round-trip drift from storing 2 decimals,
        # tightened from the old 1-decimal-place drift (100 -> 100.8)
        self.assertEqual(response.context["current_glucose_value"], 100.1)

    def test_mmol_user_sees_the_stored_value_untouched(self):
        other = User.objects.create_user(
            username="mmol", email="mmol@example.com", password="pw12345!"
        )
        GlucoseLog.objects.create(user=other, value=Decimal("5.6"))
        self.client.force_login(other)
        response = self.client.get(reverse("log-glucose"))
        self.assertEqual(response.context["unit_label"], "mmol/L")
        self.assertEqual(response.context["current_glucose_value"], 5.6)


class CrossUserIsolationTest(TestCase):
    """One user must never reach another user's medical records.

    Authorisation is enforced by `get_object_or_404(..., user=request.user)` in
    every log view. That is correct today but nothing pinned it, so a single
    dropped filter in a future refactor would leak another person's glucose,
    insulin and meal history with the whole suite still green.

    404 is asserted rather than 403 on purpose: a 403 would confirm the record
    exists, which is itself a disclosure.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="pw12345!"
        )
        self.intruder = User.objects.create_user(
            username="intruder", email="intruder@example.com", password="pw12345!"
        )
        self.glucose = GlucoseLog.objects.create(
            user=self.owner, value=Decimal("6.2"), note="owner glucose"
        )
        self.insulin = InsulinLog.objects.create(
            user=self.owner, units=Decimal("8.0"), insulin_type="bolus"
        )
        self.meal = MealLog.objects.create(
            user=self.owner, carbs=Decimal("45.0"), context="lunch"
        )
        self.client.login(email="intruder@example.com", password="pw12345!")

    def _cases(self):
        return [
            ("glucose", "edit-glucose", "delete-glucose", self.glucose),
            ("insulin", "edit-insulin", "delete-insulin", self.insulin),
            ("meal", "edit-meal", "delete-meal", self.meal),
        ]

    def test_cannot_open_another_users_edit_form(self):
        for label, edit, _delete, obj in self._cases():
            with self.subTest(model=label):
                response = self.client.get(reverse(edit, kwargs={"pk": obj.pk}))
                self.assertEqual(response.status_code, 404)

    def test_cannot_edit_another_users_record(self):
        payloads = {
            "glucose": {"value": "9.9", "context": "fasting"},
            "insulin": {"units": "99", "insulin_type": "basal"},
            "meal": {"carbs": "999", "context": "dinner"},
        }
        for label, edit, _delete, obj in self._cases():
            with self.subTest(model=label):
                before = obj.__class__.objects.get(pk=obj.pk)
                response = self.client.post(
                    reverse(edit, kwargs={"pk": obj.pk}), payloads[label]
                )
                self.assertEqual(response.status_code, 404)
                after = obj.__class__.objects.get(pk=obj.pk)
                # the owner's data must be byte-for-byte untouched
                self.assertEqual(
                    model_to_dict(before), model_to_dict(after), f"{label} was modified"
                )

    def test_cannot_delete_another_users_record(self):
        for label, _edit, delete, obj in self._cases():
            with self.subTest(model=label):
                response = self.client.post(reverse(delete, kwargs={"pk": obj.pk}))
                self.assertEqual(response.status_code, 404)
                obj.refresh_from_db()
                self.assertFalse(obj.is_deleted, f"{label} was soft-deleted")
                self.assertIsNone(obj.deleted_at)

    def test_another_users_records_never_appear_in_list_views(self):
        for name in ("log-glucose", "log-insulin", "log-meal", "glucolog-dashboard"):
            with self.subTest(view=name):
                body = self.client.get(reverse(name)).content.decode()
                self.assertNotIn("owner glucose", body)

    def test_intruder_sees_empty_aggregates_not_the_owners_totals(self):
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertIsNone(response.context["avg_glucose"])
        self.assertIsNone(response.context["total_insulin"])
        self.assertIsNone(response.context["carbs_consumed"])
        self.assertEqual(response.context["glucose_count_today"], 0)


class SoftDeleteExclusionTest(TestCase):
    """Soft-deleted medical records must disappear from reads AND from totals.

    Every query filters `is_deleted=False` by hand — there is no default
    manager enforcing it. The aggregate paths are the risk: a deleted reading
    silently included in an average or a daily carb total is wrong data
    presented as fact, and is far less visible than a row reappearing in a list.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="sd", email="sd@example.com", password="pw12345!"
        )
        self.client.login(email="sd@example.com", password="pw12345!")
        self.kept = GlucoseLog.objects.create(user=self.user, value=Decimal("6.0"))
        self.removed = GlucoseLog.objects.create(
            user=self.user, value=Decimal("12.0"), note="deleted reading"
        )
        InsulinLog.objects.create(user=self.user, units=Decimal("4.0"), insulin_type="bolus")
        self.removed_insulin = InsulinLog.objects.create(
            user=self.user, units=Decimal("10.0"), insulin_type="basal"
        )
        MealLog.objects.create(user=self.user, carbs=Decimal("30.0"), context="lunch")
        self.removed_meal = MealLog.objects.create(
            user=self.user, carbs=Decimal("70.0"), context="dinner"
        )
        for obj in (self.removed, self.removed_insulin, self.removed_meal):
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save()

    def test_deleted_reading_is_excluded_from_the_glucose_average(self):
        response = self.client.get(reverse("log-glucose"))
        # only the 6.0 remains; including 12.0 would average to 9.0
        self.assertEqual(float(response.context["avg_glucose"]), 6.0)
        self.assertEqual(response.context["reading_count"], 1)

    def test_deleted_dose_is_excluded_from_the_insulin_total(self):
        response = self.client.get(reverse("log-insulin"))
        self.assertEqual(float(response.context["total_units_today"]), 4.0)

    def test_deleted_meal_is_excluded_from_the_carb_total(self):
        response = self.client.get(reverse("log-meal"))
        self.assertEqual(float(response.context["carbs_today"]), 30.0)

    def test_dashboard_totals_exclude_deleted_records(self):
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertEqual(float(response.context["avg_glucose"]), 6.0)
        self.assertEqual(float(response.context["total_insulin"]), 4.0)
        self.assertEqual(float(response.context["carbs_consumed"]), 30.0)

    def test_deleted_record_does_not_render_in_a_list(self):
        body = self.client.get(reverse("log-glucose")).content.decode()
        self.assertNotIn("deleted reading", body)

    def test_deleted_record_is_not_reachable_by_url(self):
        self.assertEqual(
            self.client.get(
                reverse("edit-glucose", kwargs={"pk": self.removed.pk})
            ).status_code,
            404,
        )


class LogViewValidationTest(TestCase):
    """Regression tests for server-side validation in the add/edit views."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_edit_insulin_invalid_units_stays_in_edit_mode(self):
        from logs.models import InsulinLog
        from django.urls import reverse

        log = InsulinLog.objects.create(
            user=self.user, units=10, insulin_type="bolus"
        )
        response = self.client.post(
            reverse("edit-insulin", kwargs={"pk": log.pk}),
            {"units": "not-a-number", "insulin_type": "bolus"},
        )
        # must bounce back to the edit form, not silently switch to add mode
        self.assertRedirects(response, reverse("edit-insulin", kwargs={"pk": log.pk}))

    def test_add_insulin_rejects_unknown_type(self):
        from logs.models import InsulinLog
        from django.urls import reverse

        self.client.post(
            reverse("add-insulin"), {"units": "5", "insulin_type": "banana"}
        )
        self.assertFalse(InsulinLog.objects.filter(user=self.user).exists())

    def test_add_meal_rejects_negative_macros(self):
        from logs.models import MealLog
        from django.urls import reverse

        self.client.post(
            reverse("add-meal"), {"carbs": "-50", "context": "lunch"}
        )
        self.assertFalse(MealLog.objects.filter(user=self.user).exists())

    def test_add_glucose_rejects_unknown_context(self):
        from django.urls import reverse

        self.client.post(
            reverse("add-glucose"), {"value": "6.0", "context": "banana"}
        )
        self.assertFalse(GlucoseLog.objects.filter(user=self.user).exists())

    def test_add_glucose_empty_context_defaults_to_other(self):
        from django.urls import reverse

        self.client.post(reverse("add-glucose"), {"value": "6.0", "context": ""})
        log = GlucoseLog.objects.get(user=self.user)
        self.assertEqual(log.context, "other")

    def test_add_glucose_rejects_non_finite_values(self):
        """NaN and Infinity parse as Decimal but must never reach the database.

        Decimal("NaN") constructs without raising, so it slips past the parse
        guard; any later comparison against it then raises InvalidOperation.
        """
        from django.urls import reverse

        for raw in ("NaN", "sNaN", "Infinity", "-Infinity"):
            with self.subTest(value=raw):
                response = self.client.post(
                    reverse("add-glucose"), {"value": raw, "context": "fasting"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(GlucoseLog.objects.filter(user=self.user).exists())

    def test_add_meal_rejects_non_finite_macros(self):
        """Postgres numeric accepts NaN, so one bad macro would poison Sum() forever."""
        from logs.models import MealLog
        from django.urls import reverse

        for raw in ("NaN", "Infinity"):
            with self.subTest(value=raw):
                self.client.post(
                    reverse("add-meal"), {"carbs": raw, "context": "lunch"}
                )
                self.assertFalse(MealLog.objects.filter(user=self.user).exists())

    def test_daily_carb_total_survives_a_rejected_nan(self):
        """The regression that matters: totals must stay arithmetically sound."""
        from django.db.models import Sum
        from logs.models import MealLog
        from django.urls import reverse

        self.client.post(reverse("add-meal"), {"carbs": "30", "context": "lunch"})
        self.client.post(reverse("add-meal"), {"carbs": "NaN", "context": "dinner"})

        total = MealLog.objects.filter(user=self.user, is_deleted=False).aggregate(
            total=Sum("carbs")
        )["total"]
        self.assertEqual(total, 30)
        self.assertTrue(total.is_finite())


class DashboardChartOrderingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_chart_points_are_time_ordered(self):
        from django.urls import reverse

        now = timezone.now()
        # insert out of chronological order on purpose
        GlucoseLog.objects.create(user=self.user, value=7.0, measured_at=now)
        GlucoseLog.objects.create(
            user=self.user, value=5.0, measured_at=now - timedelta(hours=3)
        )
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertEqual(response.context["glucose_values"], [5.0, 7.0])
