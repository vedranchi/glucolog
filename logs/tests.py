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
