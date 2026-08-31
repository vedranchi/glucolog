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
            reverse("glucoread-login"),
            {"username": "login@example.com", "password": "pw12345!"},
        )
        self.assertRedirects(response, reverse("glucoread-dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_does_not_log_in(self):
        response = self.client.post(
            reverse("glucoread-login"),
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
        url = reverse("glucoread-login")
        creds = {"username": "rate@example.com", "password": "wrong"}
        for _ in range(5):
            self.assertEqual(self.client.post(url, creds).status_code, 200)
        self.assertEqual(self.client.post(url, creds).status_code, 403)

    def test_register_throttles_by_ip(self):
        url = reverse("glucoread-register")
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

    def test_cache_table_name_matches_the_migrations(self):
        """0001 creates the table, 0002 renames it; the name is coupled in three
        places.

        Renaming one without the others leaves every rate-limited view raising
        ProgrammingError on a real database. The test runner creates cache
        tables automatically, so no other test can catch that drift.
        """
        from importlib import import_module

        from django.conf import settings

        create = import_module("main.migrations.0001_create_cache_table")
        rename = import_module("main.migrations.0002_rename_cache_table")

        # 0002 has to rename the exact table 0001 created, ...
        self.assertEqual(create.CACHE_TABLE, rename.OLD_TABLE)
        # ... and settings has to point at what the last migration leaves behind.
        self.assertEqual(
            settings.CACHES["default"]["LOCATION"], rename.NEW_TABLE
        )


class ProfileUpdateTest(TestCase):
    """The profile page is one <form> covering three model forms at once.

    Regression coverage for the bug where a failing section (e.g. a bad
    email) saved the other, unrelated sections anyway and reported success —
    the user's actual edit vanished with no error shown.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="profileuser", email="profile@example.com", password="pw12345!"
        )
        self.client.login(email="profile@example.com", password="pw12345!")

    def _post(self, **overrides):
        data = {
            "username": self.user.username,
            "email": self.user.email,
            "glucose_unit": "mmol",
            "diabetes_type": "type1",
        }
        data.update(overrides)
        return self.client.post(reverse("user-profile"), data)

    def test_valid_edit_saves_every_section(self):
        response = self._post(username="renamed", glucose_unit="mg/dL")
        self.assertRedirects(response, reverse("user-profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed")
        self.assertEqual(self.user.preferences.glucose_unit, "mg/dL")

    def test_invalid_section_saves_nothing_and_shows_the_error(self):
        response = self._post(email="not-an-email", glucose_unit="mg/dL")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "profile@example.com")
        # a sibling section that validated fine must not be saved either --
        # the old code saved it and reported false success
        self.assertEqual(self.user.preferences.glucose_unit, "mmol")


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


class LoginNextRedirectTest(TestCase):
    """@login_required appends ?next=; sign-in used to ignore it.

    The user asked for one page, authenticated, and landed on the dashboard
    instead. `next` is validated against the current host — an unchecked one is
    an open redirect.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="nextuser", email="next@example.com", password="pw12345!"
        )

    def test_login_required_view_sends_the_user_back_where_they_asked(self):
        target = reverse("add-glucose")
        response = self.client.get(target)
        self.assertRedirects(
            response, f"{reverse('glucoread-login')}?next={target}"
        )

        response = self.client.post(
            reverse("glucoread-login"),
            {"username": "next@example.com", "password": "pw12345!", "next": target},
        )
        self.assertRedirects(response, target)

    def test_login_without_next_lands_on_the_dashboard(self):
        response = self.client.post(
            reverse("glucoread-login"),
            {"username": "next@example.com", "password": "pw12345!"},
        )
        self.assertRedirects(response, reverse("glucoread-dashboard"))

    def test_offsite_next_is_ignored(self):
        response = self.client.post(
            reverse("glucoread-login"),
            {
                "username": "next@example.com",
                "password": "pw12345!",
                "next": "https://evil.example.com/steal",
            },
        )
        self.assertRedirects(response, reverse("glucoread-dashboard"))
