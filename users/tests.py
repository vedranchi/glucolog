from django.test import TestCase
from django.core import mail
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


# view loads
class PasswordResetTest(TestCase):
    def setUp(self):
        # rate-limit counters live in the cache; clear so state cannot leak
        # between tests and trip a limit unrelated to what is being asserted
        cache.clear()

    def test_password_reset_page_loads(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)


# email is queued
class PasswordResetEmailTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="pass"
        )

    def test_password_reset_sends_email(self):
        self.client.post(reverse("password_reset"), {"email": "test@example.com"})
        self.assertEqual(len(mail.outbox), 1)


class LoginTest(TestCase):
    """Covers login_view, which authenticates via form.get_user().

    Email is the USERNAME_FIELD, so the credential is submitted in the form's
    field named "username" — the rate limiter keys off that same field.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="loginuser", email="login@example.com", password="pw12345!"
        )

    def test_valid_credentials_log_the_user_in(self):
        response = self.client.post(
            reverse("glucolog-login"),
            {"username": "login@example.com", "password": "pw12345!"},
        )
        self.assertRedirects(response, reverse("glucolog-dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_does_not_log_in(self):
        response = self.client.post(
            reverse("glucolog-login"),
            {"username": "login@example.com", "password": "nope"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class RateLimitTest(TestCase):
    """The auth endpoints send mail and verify credentials, so they must throttle."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="ratetest", email="rate@example.com", password="pw12345!"
        )

    def test_password_reset_throttles_by_target_address(self):
        """3/h per address — an inbox must not be floodable."""
        url = reverse("password_reset")
        for _ in range(3):
            self.assertEqual(
                self.client.post(url, {"email": "rate@example.com"}).status_code, 302
            )
        self.assertEqual(
            self.client.post(url, {"email": "rate@example.com"}).status_code, 403
        )
        # only the allowed attempts actually sent mail
        self.assertEqual(len(mail.outbox), 3)

    def test_login_throttles_by_username(self):
        """5/5m per credential, so one account cannot be ground down."""
        url = reverse("glucolog-login")
        creds = {"username": "rate@example.com", "password": "wrong"}
        for _ in range(5):
            self.assertEqual(self.client.post(url, creds).status_code, 200)
        self.assertEqual(self.client.post(url, creds).status_code, 403)

    def test_register_throttles_by_ip(self):
        url = reverse("glucolog-register")
        for i in range(10):
            self.client.post(url, {"username": f"u{i}", "email": f"u{i}@example.com"})
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_get_requests_are_not_throttled(self):
        """Only POSTs are limited, so a blocked visitor can still read the form."""
        cache.clear()
        url = reverse("password_reset")
        for _ in range(3):
            self.client.post(url, {"email": "rate@example.com"})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_rate_limit_cache_is_shared_not_per_process(self):
        """LocMemCache would make limits per-worker, silently 3x too lenient."""
        from django.conf import settings

        self.assertNotIn("locmem", settings.CACHES["default"]["BACKEND"].lower())
        cache.set("shared-probe", "v", 30)
        self.assertEqual(cache.get("shared-probe"), "v")

    def test_cache_table_name_matches_the_migration(self):
        """The table is created by main/0001; the name is coupled in two places.

        Renaming one without the other leaves every rate-limited view raising
        ProgrammingError on a real database. The test runner creates cache
        tables automatically, so no other test can catch that drift.
        """
        from importlib import import_module

        from django.conf import settings

        migration = import_module("main.migrations.0001_create_cache_table")
        self.assertEqual(
            settings.CACHES["default"]["LOCATION"], migration.CACHE_TABLE
        )


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
