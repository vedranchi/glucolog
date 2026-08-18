import logging

from django.conf import settings
from django.test import TestCase


class ObservabilityConfigTest(TestCase):
    """Production failures were previously invisible.

    Django's default configuration mails unhandled 500s to ADMINS and does
    nothing else. ADMINS was unset and no LOGGING dict existed, so a production
    error reached no file, no stream and no inbox — and neither would a
    brute-force run against the auth endpoints.
    """

    def test_logging_is_configured(self):
        self.assertTrue(settings.LOGGING, "no LOGGING dict — 500s would be silent")
        self.assertIn("console", settings.LOGGING["handlers"])

    def test_server_errors_reach_a_stream_and_the_admins(self):
        handlers = {type(h).__name__ for h in logging.getLogger("django.request").handlers}
        self.assertIn("StreamHandler", handlers)
        self.assertIn("AdminEmailHandler", handlers)

    def test_loglevel_env_var_is_actually_read(self):
        """DJANGO_LOGLEVEL sat in .env unread for months; keep it wired."""
        self.assertEqual(
            logging.getLevelName(logging.getLogger("django").level),
            settings.DJANGO_LOGLEVEL,
        )

    def test_db_backend_logger_is_pinned_above_debug(self):
        """django.db.backends echoes query parameters at DEBUG — health data."""
        level = logging.getLogger("django.db.backends").level
        self.assertGreaterEqual(level, logging.INFO)
