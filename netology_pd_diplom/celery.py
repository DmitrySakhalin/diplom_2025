import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')

app = Celery('backend')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
