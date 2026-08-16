from django.core.management import call_command
from django.db import migrations

CACHE_TABLE = "glucolog_cache"


def create_cache_table(apps, schema_editor):
    """Create the table backing CACHES["default"].

    The rate limiters on login, registration and password reset store their
    counters in the cache, so this table has to exist before those views can
    serve a request at all — a missing table is a 500, not a degraded limit.

    Doing it as a migration rather than leaving it to `createcachetable` means
    every environment gets it from `migrate` alone. The management command is
    easy to forget on a fresh clone, and the test runner creates cache tables
    automatically, so the omission does not show up in the test suite.
    """
    call_command(
        "createcachetable",
        CACHE_TABLE,
        database=schema_editor.connection.alias,
        verbosity=0,
    )


def drop_cache_table(apps, schema_editor):
    schema_editor.execute(f'DROP TABLE IF EXISTS "{CACHE_TABLE}"')


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]
