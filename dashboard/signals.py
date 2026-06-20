from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from users.models import UserPreferences, HealthProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_related_profiles(sender, instance, created, **kwargs):
    """Give every new user their preferences and health profile up front.

    Both are created here (previously only UserPreferences was), so the two
    one-to-one profiles stay consistent. get_or_create keeps it idempotent,
    so it never raises if a row already exists for a legacy account.
    """
    if created:
        UserPreferences.objects.get_or_create(user=instance)
        HealthProfile.objects.get_or_create(user=instance)
