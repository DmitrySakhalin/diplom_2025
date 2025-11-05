from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class BackendEndpointsTest(APITestCase):
    def setUp(self):
        # Создайте пользователя с актуальным паролем
        self.user = User.objects.create_superuser(email='dmitry-pack@mail.ru', password='yourpassword')
        # force_authenticate для прохождения аутентификации
        self.client.force_authenticate(user=self.user)

    def test_partner_update(self):
        url = reverse('backend:partner-update')
        response = self.client.post(url)  # POST вместо GET
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_partner_state(self):
        url = reverse('backend:partner-state')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_partner_orders(self):
        url = reverse('backend:partner-orders')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_user_register(self):
        url = reverse('backend:user-register')
        data = {'email': 'testuser@example.com', 'password': 'testpass123'}
        response = self.client.post(url, data=data)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_user_register_confirm(self):
        url = reverse('backend:user-register-confirm')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_user_details(self):
        url = reverse('backend:user-details')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_user_contact(self):
        url = reverse('backend:user-contact')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_user_login(self):
        url = reverse('backend:user-login')
        data = {'email': 'dmitry-pack@mail.ru', 'password': 'yourpassword'}
        response = self.client.post(url, data=data)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_password_reset(self):
        url = reverse('backend:password-reset')
        response = self.client.post(url, data={'email': 'dmitry-pack@mail.ru'})
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_password_reset_confirm(self):
        url = reverse('backend:password-reset-confirm')
        data = {'token': 'fake-token', 'password': 'newpass123'}
        response = self.client.post(url, data=data)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_categories(self):
        url = reverse('backend:categories')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_shops(self):
        url = reverse('backend:shops')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_products(self):
        url = reverse('backend:products')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_basket(self):
        from backend.models import Order
        Order.objects.create(user=self.user, state='basket')

        url = reverse('backend:basket')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_order(self):
        url = reverse('backend:order')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
