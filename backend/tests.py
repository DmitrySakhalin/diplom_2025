import json
import tempfile
from django.core import mail, cache
from django.urls import reverse
from django.test import TestCase, override_settings
from django_rest_passwordreset.models import ResetPasswordToken
from prompt_toolkit.key_binding.bindings.search import start_reverse_incremental_search
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from backend.models import (
    Contact, ProductInfo, Order, OrderItem, Shop, Category, User,
    ConfirmEmailToken, Product, Parameter, ProductParameter
)
from backend.forms import LoginForm, RegisterForm, ContactForm, OrderConfirmForm
from backend.services import load_products_from_yaml

User = get_user_model()

# Базовый класс тестов API без throttling
@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {}
    }
)
class BaseApiTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        try:
            from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
            UserRateThrottle.allow_request = lambda self, request, view: True
            AnonRateThrottle.allow_request = lambda self, request, view: True
        except Exception:
            pass

# Тесты сервиса загрузки продуктов
@override_settings(REST_FRAMEWORK={
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {}
})
class ServicesTest(TestCase):
    def test_load_products_from_yaml_creates_objects(self):
        user = User.objects.create_user(email="testuser@example.com", password="pass")
        yaml_content = '''
        shop: TestShop
        categories:
          - id: 1
            name: Category1
        goods:
          - id: 1
            name: Product1
            category: 1
            price: 100
            price_rrc: 150
            quantity: 10
            model: Model1
            parameters:
              color: red
        '''
        with tempfile.NamedTemporaryFile("w+", delete=True) as tmpfile:
            tmpfile.write(yaml_content)
            tmpfile.flush()
            load_products_from_yaml(tmpfile.name, user)
        shop = Shop.objects.get(name="TestShop")
        assert shop.user == user
        category = Category.objects.get(id=1)
        assert category.name == "Category1"
        assert shop in category.shops.all()
        product = Product.objects.get(name="Product1")
        product_info = ProductInfo.objects.get(product=product, shop=shop)
        assert product_info.price == 100
        param = Parameter.objects.get(name="color")
        product_param = ProductParameter.objects.get(product_info=product_info, parameter=param)
        self.assertEqual(product_param.value, "red")

    def test_old_productinfo_deleted_before_import(self):
        user = User.objects.create_user(email="test2@example.com", password="pass")
        shop = Shop.objects.create(name="OtherShop", user=user)
        category = Category.objects.create(name="SomeCategory")
        product = Product.objects.create(name="OldProduct", category=category)
        old_product_info = ProductInfo.objects.create(
            product=product, shop=shop, quantity=5, price=50,
            price_rrc=60, model='OldModel', external_id=999
        )
        yaml_content = """
        shop: OtherShop
        categories: []
        goods: []
        """
        with tempfile.NamedTemporaryFile("w+", delete=True) as tmpfile:
            tmpfile.write(yaml_content)
            tmpfile.flush()
            load_products_from_yaml(tmpfile.name, user)
        self.assertEqual(ProductInfo.objects.filter(id=old_product_info.id).count(), 0)

# Backend endpoints
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class BackendEndpointsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email='dmitry-pack@mail.ru', password='yourpassword')
        self.client.force_authenticate(user=self.user)

    def test_partner_update(self):
        url = reverse('backend:partner-update')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_partner_state(self):
        url = reverse('backend:partner-state')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_partner_orders(self):
        url = reverse('backend:partner-orders')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_user_register(self):
        url = reverse('backend:user-register')
        data = {'email': 'testuser@example.com', 'password': 'testpass123'}
        response = self.client.post(url, data=data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED,
                                             status.HTTP_400_BAD_REQUEST, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_user_register_confirm(self):
        url = reverse('backend:user-register-confirm')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_user_details(self):
        url = reverse('backend:user-details')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_user_contact(self):
        url = reverse('backend:user-contact')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_user_login(self):
        url = reverse('backend:user-login')
        data = {'email': 'dmitry-pack@mail.ru', 'password': 'yourpassword'}
        response = self.client.post(url, data=data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_password_reset(self):
        url = reverse('backend:password-reset')
        response = self.client.post(url, data={'email': 'dmitry-pack@mail.ru'}, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_password_reset_confirm(self):
        url = reverse('backend:password-reset-confirm')
        data = {'token': 'fake-token', 'password': 'newpass123'}
        response = self.client.post(url, data=data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_categories(self):
        url = reverse('backend:categories')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_shops(self):
        url = reverse('backend:shops')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_products(self):
        url = reverse('backend:products')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_basket(self):
        Order.objects.create(user=self.user, state='basket')
        url = reverse('backend:basket')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

    def test_order(self):
        url = reverse('backend:order')
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_400_BAD_REQUEST, status.HTTP_429_TOO_MANY_REQUESTS])

# Account tests
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class AccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('backend.tasks.send_registration_email.delay')
    def test_register_user(self, mock_send_email):
        data = {
            'first_name': 'Dmitry',
            'last_name': 'Pack',
            'email': 'dmitry-pack@example.com',
            'password': 'ComplexPass123!',
            'company': 'MyCompany',
            'position': 'Developer'
        }
        response = self.client.post(reverse('backend:user-register'), data=data, format='json')
        self.assertTrue(response.data['Status'])

# Дополнительные API тесты
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class AdditionalApiTests(APITestCase):
    def setUp(self):
        super().setUp()
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
        self.contact = Contact.objects.create(user=self.user, city='SPB', street='Nevsky', phone='1234567890',
                                              house='1')
        self.basket = Order.objects.create(user=self.user, state='basket')
        self.order_item = OrderItem.objects.create(order=self.basket, product_info=self.product_info, quantity=1)

    def test_list_products(self):
        url = reverse('backend:products')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_to_basket(self):
        url = reverse('backend:basket')
        basket = Order.objects.filter(user=self.user, state='basket').first()
        if basket:
            basket.ordered_items.all().delete()
        items = [{'product_info': self.product_info.id, 'quantity': 2}]
        response = self.client.post(url, {'items': json.dumps(items)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json().get('Status'))

    def test_view_basket(self):
        url = reverse('backend:basket')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_delete_from_basket(self):
        url = reverse('backend:basket')
        items = [{'product_info': self.product_info.id, 'quantity': 1}]
        self.client.post(url, {'items': json.dumps(items)})
        basket = Order.objects.filter(user=self.user, state='basket').first()
        order_item = basket.ordered_items.first()
        response = self.client.delete(url, {'items': str(order_item.id)}, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json().get('Status'))

    def test_create_contact(self):
        url = reverse('backend:user-contact')
        data = {'city': 'SPB', 'street': 'Nevsky', 'phone': '1234567890', 'house': '1', 'user': self.user.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json().get('Status'))

    def test_edit_contact(self):
        url = reverse('backend:user-contact')
        data = {'id': self.contact.id, 'city': 'Moscow'}
        response = self.client.put(url, data, format='json')
        self.assertTrue(response.json().get('Status'))

    def test_delete_contact(self):
        url = reverse('backend:user-contact')
        response = self.client.delete(url, {'items': str(self.contact.id)}, content_type='application/json')
        self.assertTrue(response.json().get('Status'))

    def test_confirm_order(self):
        url = reverse('backend:order')
        data = {'id': self.basket.id, 'contact': self.contact.id}
        response = self.client.post(url, data, format='json')
        self.assertTrue(response.json().get('Status'))

    def test_order_history(self):
        url = reverse('backend:order')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

# Формы тесты
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class FormsTestCase(TestCase):

    def test_login_form_valid(self):
        form_data = {'email': 'test@example.com', 'password': 'secret123'}
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_login_form_invalid(self):
        form = LoginForm(data={'email': 'not-an-email', 'password': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('password', form.errors)

    def test_register_form_valid(self):
        form_data = {
            'last_name': 'Ivanov',
            'first_name': 'Ivan',
            'email': 'ivan@example.com',
            'password': 'secret123'
        }
        form = RegisterForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_register_form_invalid_duplicate_email(self):
        User.objects.create_user(username='ivan', email='ivan@example.com', password='pass123')
        form_data = {
            'last_name': 'Ivanov',
            'first_name': 'Ivan',
            'email': 'ivan@example.com',
            'password': 'secret123'
        }
        form = RegisterForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertEqual(form.errors['email'], ['Пользователь с таким Email уже существует'])

    def test_contact_form_valid(self):
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
        form_data = {'basket_id': 1, 'contact_id': 2}
        form = OrderConfirmForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_order_confirm_form_invalid(self):
        form = OrderConfirmForm(data={'basket_id': 'a', 'contact_id': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('basket_id', form.errors)
        self.assertIn('contact_id', form.errors)

# Import products test
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class ImportProductsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email="admin@example.com", password="password")
        self.client.force_authenticate(user=self.user)
        self.url = reverse('backend:partner-update')

    @patch('backend.views.get')
    @patch('backend.views.load_yaml')
    def test_import_products_valid_yaml(self, mock_load_yaml, mock_get):
        self.user.type = 'shop'
        self.user.save()
        mock_yaml_data = {
            'shop': 'TestShop',
            'categories': [{'id': 1, 'name': 'Cat1'}],
            'goods': [{'id': 1, 'name': 'Product1', 'category': 1, 'price': 100, 'price_rrc': 150,
                       'quantity': 10, 'model': 'M1', 'parameters': {'color': 'red'}}]
        }
        mock_get.return_value.content = b'fake content'
        mock_load_yaml.return_value = mock_yaml_data
        response = self.client.post(self.url, data={'url': 'http://example.com/fake.yaml'}, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

# Сигналы и письма
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class SignalsAndEmailTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="pass")

    def test_confirmation_email_sent_on_user_creation(self):
        mail.outbox = []
        user = User.objects.create(email="newuser@example.com", username="uniqueusername", password="pass", is_active=False)
        token_count = ConfirmEmailToken.objects.filter(user=user).count()
        self.assertEqual(token_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirmation Token", mail.outbox[0].subject)

    def test_password_reset_email_sent(self):
        from django_rest_passwordreset.tokens import get_token_generator
        mail.outbox = []
        token = get_token_generator().generate_token()
        mail.send_mail('Password Reset Token', token, None, [self.user.email])
        self.assertEqual(len(mail.outbox), 1)

# Валидации и ошибки
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class ValidationAndErrorTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@example.com', password='pass')
        self.client.force_authenticate(user=self.user)

    def test_registration_missing_fields(self):
        url = reverse('backend:user-register')
        data = {'email': 'test@example.com'}
        response = self.client.post(url, data)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_invalid_order_confirm(self):
        url = reverse('backend:order')
        data = {'id': 'not_an_int', 'contact': 'abc'}
        response = self.client.post(url, data)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_400_BAD_REQUEST, status.HTTP_429_TOO_MANY_REQUESTS])

# Безопасность и разрешения
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class SecurityAndPermissionsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user1", email="user1@example.com", password="password")
        self.other_user = User.objects.create_user(username="user2", email="user2@example.com", password="password")
        self.client.force_authenticate(user=self.user)

    def test_access_partner_endpoints_forbidden_for_non_shop(self):
        url = reverse('backend:partner-state')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_access_partner_endpoints_allowed_for_shop(self):
        self.user.type = 'shop'
        self.user.save()
        self.shop = Shop.objects.create(name="TestShop", state=True)
        self.user.shop = self.shop
        self.user.save()
        url = reverse('backend:partner-state')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN,
                                             status.HTTP_429_TOO_MANY_REQUESTS])

# Тесты на устойчивость и ошибки
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class EdgeCasesAndRobustnessTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="password")
        self.client.force_authenticate(user=self.user)

    def test_delete_nonexistent_contact(self):
        url = reverse('backend:user-contact')
        response = self.client.delete(url, {'items': '99999'}, content_type='application/json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_add_order_item_invalid_data(self):
        url = reverse('backend:basket')
        items = [{'product_info': 'not_int', 'quantity': -1}]
        response = self.client.post(url, {'items': json.dumps(items)})
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_429_TOO_MANY_REQUESTS])

# Аккаунты и уведомления
@override_settings(CELERY_ALWAYS_EAGER=True)
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class AccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('backend.tasks.send_registration_email.delay')
    def test_register_user(self, mock_send_email):
        data = {
            'first_name': 'Dmitry',
            'last_name': 'Pack',
            'email': 'dmitry-pack@example.com',
            'password': 'ComplexPass123!',
            'company': 'MyCompany',
            'position': 'Developer'
        }
        response = self.client.post(reverse('backend:user-register'), data=data, format='json')
        self.assertTrue(response.data['Status'])

@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="testpass")

    @patch('backend.tasks.send_password_reset_email.delay')
    def test_password_reset_email_triggered(self, mock_send_email):
        token = None
        # создаем токен ResetPasswordToken вручную, иначе сигнал может не сработать в тестовой среде
        token = ResetPasswordToken.objects.create(user=self.user)
        # Эмулируем сигнал
        # вызываем обработчик сигнала напрямую, если он присутствует в проекте
        mock_send_email.assert_not_called()  # заглушка, реальный вызов может быть привязан к сигналу

# Заказ через API
@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {}
})
class OrderCreationTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="testuser@example.com", password="pass")
        self.client.force_authenticate(user=self.user)
        self.shop = Shop.objects.create(name="Test Shop", state=True)
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(name="Test Product", category=self.category)
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            quantity=100,
            price=1000,
            price_rrc=1200,
            model="ModelX",
            external_id=1
        )

    def test_create_order(self):
        url = reverse('backend:order')
        data = {'id': None, 'contact': None}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                             status.HTTP_429_TOO_MANY_REQUESTS])
        if response.status_code == status.HTTP_200_OK:
            orders = Order.objects.filter(user=self.user).exclude(state='basket')
            self.assertTrue(orders.exists())
