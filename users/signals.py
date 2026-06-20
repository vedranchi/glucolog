from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserPreferences, HealthProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_related_profiles(sender, instance, created, **kwargs):
    """Ensure every new user gets their preferences and health profile.

    Attached to the project's custom user model via AUTH_USER_MODEL so it
    actually fires. get_or_create keeps it idempotent, so re-saving an
    existing user never raises a duplicate OneToOne error.
    """
    if created:
        UserPreferences.objects.get_or_create(user=instance)
        HealthProfile.objects.get_or_create(user=instance)
