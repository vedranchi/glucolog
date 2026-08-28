from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from logs.models import GlucoseLog, InsulinLog, MealLog

User = get_user_model()


class DashboardAccessTest(TestCase):
    def test_redirect_if_not_logged_in(self):
        self.client.logout()
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertEqual(response.status_code, 302)


class DashboardContextTest(TestCase):
    def setUp(self):
        # email is the USERNAME_FIELD, so login must use the email credential
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_dashboard_context_contains_recent_activity(self):
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertIn("recent_activity", response.context)


class DashboardAggregationTest(TestCase):
    """Covers the DB-level aggregation that replaced summing querysets in Python."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="agguser", email="agg@example.com", password="pw12345!"
        )
        self.client.login(email="agg@example.com", password="pw12345!")

    def test_averages_and_totals_reflect_todays_logs(self):
        GlucoseLog.objects.create(user=self.user, value=Decimal("5.0"))
        GlucoseLog.objects.create(user=self.user, value=Decimal("7.0"))
        InsulinLog.objects.create(
            user=self.user, insulin_type="bolus", units=Decimal("2.5")
        )
        MealLog.objects.create(user=self.user, carbs=Decimal("30.0"))
        # a meal with no carbs entered must not crash SUM or drop the other total
        MealLog.objects.create(user=self.user, carbs=None)

        response = self.client.get(reverse("glucolog-dashboard"))

        self.assertEqual(response.context["avg_glucose"], Decimal("6.0"))
        self.assertEqual(response.context["total_insulin"], Decimal("2.5"))
        self.assertEqual(response.context["carbs_consumed"], Decimal("30.0"))
        self.assertEqual(response.context["glucose_count_today"], 2)
        self.assertEqual(response.context["meal_count_today"], 2)

    def test_no_logs_today_reports_none_not_zero(self):
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertIsNone(response.context["avg_glucose"])
        self.assertIsNone(response.context["total_insulin"])
        self.assertIsNone(response.context["carbs_consumed"])