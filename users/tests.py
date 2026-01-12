from django.test import TestCase
from django.core import mail
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


# view loads
class PasswordResetTest(TestCase):
    def test_password_reset_page_loads(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)


# email is queued
class PasswordResetEmailTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="pass"
        )

    def test_password_reset_sends_email(self):
        self.client.post(reverse("password_reset"), {"email": "test@example.com"})
        self.assertEqual(len(mail.outbox), 1)
