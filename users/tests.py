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


class NoPublicTokenEndpointsTest(TestCase):
    """The JWT endpoints were public, unthrottled and served no API.

    They verified credentials for anyone who asked and issued tokens that
    could not be revoked. Nothing consumed them. If an API is built later it
    needs throttling and a token blacklist, so these must not come back by
    accident.
    """

    def test_token_endpoints_are_gone(self):
        for url in ("/users/api/token/", "/users/api/token/refresh/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 404)
