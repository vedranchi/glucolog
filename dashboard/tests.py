from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class DashboardAccessTest(TestCase):
    def test_redirect_if_not_logged_in(self):
        self.client.logout()
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertEqual(response.status_code, 302)


class DashboardContextTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test", password="test123")
        self.client.login(username="test", password="test123")


    def test_dashboard_context_contains_recent_activity(self):
        response = self.client.get(reverse("glucolog-dashboard"))
        self.assertIn("recent_activity", response.context)