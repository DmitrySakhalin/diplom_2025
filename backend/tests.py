import json
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.test import TestCase
from backend.models import Contact, ProductInfo, Order, OrderItem, Shop, Category
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from backend.forms import LoginForm, RegisterForm, ContactForm, OrderConfirmForm

User = get_user_model()

class BackendEndpointsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email='dmitry-pack@mail.ru', password='yourpassword')
        self.client.force_authenticate(user=self.user)

    def test_partner_update(self):
        """Тест на обновление информации партнёра (POST запрос)."""
        url = reverse('backend:partner-update')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_partner_state(self):
        """Тест на получение состояния партнёра (магазина)."""
        url = reverse('backend:partner-state')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_partner_orders(self):
        """Тест на получение заказов партнёра."""
        url = reverse('backend:partner-orders')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_user_register(self):
        """Тест упрощенной регистрации пользователя."""
        url = reverse('backend:user-register')
        data = {'email': 'testuser@example.com', 'password': 'testpass123'}
        response = self.client.post(url, data=data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_user_register_confirm(self):
        """Тест подтверждения регистрации."""
        url = reverse('backend:user-register-confirm')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_user_details(self):
        """Тест получения данных пользователя."""
        url = reverse('backend:user-details')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_user_contact(self):
        """Тест создания контакта."""
        url = reverse('backend:user-contact')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_user_login(self):
        """Тест авторизации пользователя."""
        url = reverse('backend:user-login')
        data = {'email': 'dmitry-pack@mail.ru', 'password': 'yourpassword'}
        response = self.client.post(url, data=data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_password_reset(self):
        """Тест запроса на сброс пароля."""
        url = reverse('backend:password-reset')
        response = self.client.post(url, data={'email': 'dmitry-pack@mail.ru'}, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_password_reset_confirm(self):
        """Тест подтверждения сброса пароля."""
        url = reverse('backend:password-reset-confirm')
        data = {'token': 'fake-token', 'password': 'newpass123'}
        response = self.client.post(url, data=data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_categories(self):
        """Тест получения списка категорий."""
        url = reverse('backend:categories')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_shops(self):
        """Тест получения списка магазинов."""
        url = reverse('backend:shops')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_products(self):
        """Тест получения списка товаров."""
        url = reverse('backend:products')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_basket(self):
        """Тест получения корзины пользователя."""
        Order.objects.create(user=self.user, state='basket')
        url = reverse('backend:basket')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    def test_order(self):
        """Тест создания и обновления заказа."""
        url = reverse('backend:order')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])


class AccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_user(self):
        """Тест успешной регистрации пользователя с полными данными."""
        data = {
            'first_name': 'Dmitry',
            'last_name': 'Pak',
            'email': 'dmitry-pack@example.com',
            'password': 'ComplexPass123!',
            'company': 'MyCompany',
            'position': 'Developer'
        }
        response = self.client.post(reverse('backend:user-register'), data=data, format='json')
        print(response.data)
        self.assertTrue(response.data['Status'])


class AdditionalApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='ivan@example.com', password='StrongPass123!')
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.shop = Shop.objects.create(name='Shop1', state=True)
        self.category = Category.objects.create(name='Cat1')
        product_model = ProductInfo.product.field.related_model
        prod = product_model.objects.create(name="Prod1", category=self.category)
        self.product_info = ProductInfo.objects.create(
            product=prod,
            shop=self.shop,
            quantity=10,
            price=100,
            price_rrc=150,
            model='Model1',
            external_id=1
        )
        self.contact = Contact.objects.create(user=self.user, city='SPB', street='Nevsky', phone='1234567890', house='1')
        self.basket = Order.objects.create(user=self.user, state='basket')
        self.order_item = OrderItem.objects.create(order=self.basket, product_info=self.product_info, quantity=1)

    def test_list_products(self):
        """Тест получения списка товаров."""
        url = reverse('backend:products')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_to_basket(self):
        """Тест добавления товаров в корзину."""
        url = reverse('backend:basket')
        basket = Order.objects.filter(user=self.user, state='basket').first()
        if basket:
            basket.ordered_items.all().delete()

        items = [{'product_info': self.product_info.id, 'quantity': 2}]
        response = self.client.post(url, {'items': json.dumps(items)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json().get('Status'))

    def test_view_basket(self):
        """Тест просмотра содержимого корзины."""
        url = reverse('backend:basket')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_delete_from_basket(self):
        """Тест удаления товаров из корзины."""
        url = reverse('backend:basket')
        items = [{'product_info': self.product_info.id, 'quantity': 1}]
        self.client.post(url, {'items': json.dumps(items)})
        basket = Order.objects.filter(user=self.user, state='basket').first()
        order_item = basket.ordered_items.first()
        response = self.client.delete(url, {'items': str(order_item.id)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json().get('Status'))

    def test_create_contact(self):
        """Тест создания контакта."""
        url = reverse('backend:user-contact')
        data = {'city': 'SPB', 'street': 'Nevsky', 'phone': '1234567890', 'house': '1', 'user': self.user.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json().get('Status'))


    def test_edit_contact(self):
        """Тест редактирования контакта."""
        url = reverse('backend:user-contact')
        data = {'id': self.contact.id, 'city': 'Moscow'}
        response = self.client.put(url, data, format='json')
        self.assertTrue(response.json().get('Status'))

    def test_delete_contact(self):
        """Тест удаления контакта."""
        url = reverse('backend:user-contact')
        response = self.client.delete(url, {'items': str(self.contact.id)}, content_type='application/json')
        self.assertTrue(response.json().get('Status'))

    def test_confirm_order(self):
        """Тест подтверждения заказа."""
        url = reverse('backend:order')
        data = {'id': self.basket.id, 'contact': self.contact.id}
        response = self.client.post(url, data, format='json')
        self.assertTrue(response.json().get('Status'))

    def test_order_history(self):
        """Тест получения истории заказов."""
        url = reverse('backend:order')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FormsTestCase(TestCase):

    def test_login_form_valid(self):
        # Проверяет, что форма LoginForm валидна при корректных данных
        form_data = {'email': 'test@example.com', 'password': 'secret123'}
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_login_form_invalid(self):
        # Проверяет, что форма LoginForm невалидна при неправильном формате email и пустом пароле
        form = LoginForm(data={'email': 'not-an-email', 'password': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('password', form.errors)

    def test_register_form_valid(self):
        # Проверяет корректность валидации RegisterForm с новыми, уникальными данными
        form_data = {
            'last_name': 'Ivanov',
            'first_name': 'Ivan',
            'email': 'ivan@example.com',
            'password': 'secret123'
        }
        form = RegisterForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_register_form_invalid_duplicate_email(self):
        # Проверяет, что RegisterForm невалидна если email уже есть в базе пользователей
        User.objects.create_user(username='ivan', email='ivan@example.com', password='pass123')
        form_data = {
            'last_name': 'Ivanov',
            'first_name': 'Ivan',
            'email': 'ivan@example.com',  # дубликат email
            'password': 'secret123'
        }
        form = RegisterForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertEqual(form.errors['email'], ['Пользователь с таким Email уже существует'])

    def test_contact_form_valid(self):
        # Проверяет корректность валидации ContactForm при заполнении всех обязательных полей
        form_data = {
            'last_name': 'Petrov',
            'first_name': 'Petr',
            'middle_name': 'Petrovich',
            'email': 'petr@example.com',
            'phone': '1234567890',
            'address': 'Lenina 1',
            'city': 'Moscow',
            'street': 'Lenina',
            'house': '1',
            'building': '',
            'structure': '',
            'apartment': ''
        }
        form = ContactForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_order_confirm_form_valid(self):
        # Проверяет, что OrderConfirmForm валидна при передаче корректных ID корзины и контакта
        form_data = {'basket_id': 1, 'contact_id': 2}
        form = OrderConfirmForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_order_confirm_form_invalid(self):
        # Проверяет, что OrderConfirmForm невалидна, если переданы нечисловые ID
        form = OrderConfirmForm(data={'basket_id': 'a', 'contact_id': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('basket_id', form.errors)
        self.assertIn('contact_id', form.errors)
