from django.db import migrations

OLD_TABLE = "glucolog_cache"
NEW_TABLE = "glucoread_cache"


def rename(schema_editor, old, new):
    """Rename the cache table to follow the GlucoRead rename.

    0001 is left creating the old name on purpose: it is already applied in
    production, so editing it would change nothing there while breaking fresh
    installs, which would then create the new name and find nothing to rename.
    Renaming forward here keeps both paths converging on the same schema.

    IF EXISTS covers the one state 0001 cannot guarantee — a table dropped by
    hand — where failing the whole migration would be worse than letting
    `createcachetable` recreate it.
    """
    schema_editor.execute(f'ALTER TABLE IF EXISTS "{old}" RENAME TO "{new}"')


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0001_create_cache_table"),
    ]

    operations = [
        migrations.RunPython(
            lambda apps, se: rename(se, OLD_TABLE, NEW_TABLE),
            lambda apps, se: rename(se, NEW_TABLE, OLD_TABLE),
        ),
    ]
