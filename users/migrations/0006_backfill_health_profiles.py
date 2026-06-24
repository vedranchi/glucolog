from django.db import migrations


def create_missing_health_profiles(apps, schema_editor):
    """Give every existing user a HealthProfile if they don't already have one.

    New users get one at signup via the post_save signal, but accounts
    created before that was wired up are missing the related row. Use the
    field default for diabetes_type; users can change it later.
    """
    User = apps.get_model("users", "User")
    HealthProfile = apps.get_model("users", "HealthProfile")

    for user in User.objects.filter(health_profile__isnull=True):
        HealthProfile.objects.create(user=user)


def remove_health_profiles(apps, schema_editor):
    # No-op: we can't tell backfilled rows from genuinely created ones,
    # so reversing would risk deleting real data. Leave them in place.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_user_image'),
    ]

    operations = [
        migrations.RunPython(create_missing_health_profiles, remove_health_profiles),
    ]
