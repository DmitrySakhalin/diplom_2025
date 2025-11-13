"""netology_pd_diplom URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path, include
from baton.autodiscover import admin  # импорт админки из django-baton

urlpatterns = [
    path('admin/', admin.site.urls),        # Батон админка
    path('baton/', include('baton.urls')),  # Батон дополнительные url (по желанию)
    path('api/', include(('backend.urls', 'backend'), namespace='backend')),  # API backend с namespace
    path('auth/', include('social_django.urls', namespace='social')),        # Соцавторизация с namespace
    path('', include('backend.urls')),      # Основные роуты приложения без namespace
]
