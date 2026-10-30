from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Profile


@receiver(post_save, sender=get_user_model())
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def remember_previous_login(sender, request, user, **kwargs):
    """Храним дату предыдущего входа — чтобы чужое посещение было заметно."""
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.previous_login = profile.current_login
    profile.current_login = timezone.now()
    profile.save(update_fields=["previous_login", "current_login"])
