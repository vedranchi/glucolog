from django.test import TestCase
from django.contrib.auth import get_user_model
from logs.models import GlucoseLog
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

    def test_string_representation(self):
        log = GlucoseLog.objects.create(
            user=self.user, value=5.8, measured_at="2025-01-01T21:00:00Z"
        )
        # test string representation
        self.assertIn("5.8", str(log))


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
    def test_mmol_to_mgdl(self):
        mmol = 5.5
        mgdl = round(mmol * 18, 1)
        self.assertEqual(mgdl, 99.0)


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
