from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created
from rest_framework.authtoken.models import Token
from backend.models import ConfirmEmailToken, User
from backend.tasks import send_registration_email, send_password_reset_email, send_order_status_email

new_user_registered = Signal()
new_order = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    send_password_reset_email.delay(reset_password_token.user.pk, reset_password_token.key)



@receiver(post_save, sender=User)
def new_user_registered_signal(sender, instance, created, **kwargs):
    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)
        send_registration_email.delay(instance.pk, token.key)


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    send_order_status_email.delay(user_id)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    """
    Автоматически создаём токен после регистрации пользователя
    """
    if created:
        Token.objects.create(user=instance)
