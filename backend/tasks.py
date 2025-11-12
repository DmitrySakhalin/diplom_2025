import logging
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from backend.models import User

logger = logging.getLogger('celery')

@shared_task
def send_registration_email(user_id, token_key):
    logger.info(f'Start sending registration email to user {user_id} with token {token_key}')
    try:
        user = User.objects.get(id=user_id)
        subject = f"Confirmation Token for {user.email}"
        email_body = f"Ваш токен подтверждения: {token_key}"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not from_email:
            logger.error("DEFAULT_FROM_EMAIL not set in settings.py")
            return
        msg = EmailMultiAlternatives(subject, email_body, from_email, [user.email])
        msg.send()
        logger.info(f"Registration email sent to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist")
    except Exception as e:
        logger.error(f"Error sending registration email: {e}")


@shared_task
def send_password_reset_email(user_id, token_key):
    logger.info(f'Start sending password reset email to user {user_id} with token {token_key}')
    try:
        user = User.objects.get(id=user_id)
        subject = f"Password Reset Token for {user.email}"
        email_body = f"Ваш токен для сброса пароля: {token_key}"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not from_email:
            logger.error("DEFAULT_FROM_EMAIL not set in settings.py")
            return
        msg = EmailMultiAlternatives(subject, email_body, from_email, [user.email])
        msg.send()
        logger.info(f"Password reset email sent to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist")
    except Exception as e:
        logger.error(f"Error sending password reset email: {e}")


@shared_task
def send_order_status_email(user_id, order_status='Заказ сформирован'):
    logger.info(f'Start sending order status email to user {user_id} with status {order_status}')
    try:
        user = User.objects.get(id=user_id)
        subject = "Обновление статуса заказа"
        email_body = order_status
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not from_email:
            logger.error("DEFAULT_FROM_EMAIL not set in settings.py")
            return
        msg = EmailMultiAlternatives(subject, email_body, from_email, [user.email])
        msg.send()
        logger.info(f"Order status email sent to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist")
    except Exception as e:
        logger.error(f"Error sending order status email: {e}")
