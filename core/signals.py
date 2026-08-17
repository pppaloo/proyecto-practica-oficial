from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LoginLog, Perfil


@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)


@receiver(user_logged_in)
def registrar_login(sender, request, user, **kwargs):
    LoginLog.objects.create(usuario=user, accion="login")


@receiver(user_logged_out)
def registrar_logout(sender, request, user, **kwargs):
    LoginLog.objects.create(usuario=user, accion="logout")
