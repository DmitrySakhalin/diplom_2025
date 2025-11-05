from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json
from django.http import JsonResponse
from distutils.util import strtobool
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from requests import get
from yaml import load as load_yaml, Loader

from backend.models import Shop, Category, ProductInfo, Parameter, ProductParameter, Order, OrderItem, Contact, ConfirmEmailToken, Product
from backend.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, OrderItemSerializer, OrderSerializer, ContactSerializer
from backend.signals import new_user_registered, new_order


class PartnerUpdate(APIView):
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if not url:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

        validate_url = URLValidator()
        try:
            validate_url(url)
        except DjangoValidationError as e:
            return JsonResponse({'Status': False, 'Error': str(e)})

        try:
            stream = get(url).content
            data = load_yaml(stream, Loader=Loader)
        except Exception as e:
            return JsonResponse({'Status': False, 'Error': f'Error fetching or parsing YAML: {str(e)}'})

        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
            category_object.shops.add(shop)
            category_object.save()

        ProductInfo.objects.filter(shop=shop).delete()

        for item in data.get('goods', []):
            product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
            product_info = ProductInfo.objects.create(
                product_id=product.id,
                external_id=item['id'],
                model=item.get('model', ''),
                price=item['price'],
                price_rrc=item['price_rrc'],
                quantity=item['quantity'],
                shop_id=shop.id
            )
            for name, value in item.get('parameters', {}).items():
                param_obj, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(product_info=product_info, parameter=param_obj, value=value)

        return JsonResponse({'Status': True})


class RegisterAccount(APIView):
    def post(self, request: Request):
        required_fields = {'first_name', 'last_name', 'email', 'password', 'company', 'position'}
        if not required_fields.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            validate_password(request.data['password'])
        except ValidationError as exc:
            return JsonResponse({'Status': False, 'Errors': {'password': exc.messages}})

        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.set_password(request.data['password'])
            user.save()
            new_user_registered.send(sender=self.__class__, user_id=user.id)
            return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': serializer.errors})


class ConfirmAccount(APIView):
    def post(self, request: Request):
        if not {'email', 'token'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

        token = ConfirmEmailToken.objects.filter(
            user__email=request.data['email'],
            key=request.data['token']
        ).first()

        if token:
            token.user.is_active = True
            token.user.save()
            token.delete()
            return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'}, status=400)


class LoginAccount(APIView):
    def post(self, request, *args, **kwargs):
        if not {'email', 'password'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})
        user = authenticate(request=request, username=request.data['email'], password=request.data['password'])
        if user is not None and user.is_active:
            token, _ = Token.objects.get_or_create(user=user)
            return JsonResponse({'Status': True, 'Token': token.key})
        return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})


class CategoryView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    def get(self, request: Request):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')
        if shop_id:
            query &= Q(shop_id=shop_id)
        if category_id:
            query &= Q(product__category_id=category_id)

        queryset = ProductInfo.objects.filter(query).select_related('shop', 'product__category') \
            .prefetch_related('product_parameters__parameter').distinct()
        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class BasketView(APIView):
    def get(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        basket = Order.objects.filter(user=request.user, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).annotate(
            total_price_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).first()
        if not basket:
            return JsonResponse({'Status': False, 'Error': 'Корзина не найдена'}, status=404)
        serializer = OrderSerializer(basket)
        return Response(serializer.data)

    def post(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        items_str = request.data.get('items')
        if not items_str:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)
        try:
            items = load_json(items_str)
        except ValueError:
            return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'}, status=400)
        basket, _ = Order.objects.get_or_create(user=request.user, state='basket')
        created_count = 0
        for item in items:
            item['order'] = basket.id
            serializer = OrderItemSerializer(data=item)
            if serializer.is_valid():
                try:
                    serializer.save()
                    created_count += 1
                except IntegrityError as e:
                    return JsonResponse({'Status': False, 'Errors': str(e)}, status=400)
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)
        return JsonResponse({'Status': True, 'Создано объектов': created_count})

    def delete(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        items_str = request.data.get('items')
        if not items_str:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)
        item_ids = [int(i) for i in items_str.split(',') if i.isdigit()]
        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket:
            return JsonResponse({'Status': False, 'Error': 'Корзина не найдена'}, status=404)
        deleted_count, _ = OrderItem.objects.filter(order=basket, id__in=item_ids).delete()
        return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

    def put(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        items_str = request.data.get('items')
        if not items_str:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)
        try:
            items = load_json(items_str)
        except ValueError:
            return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'}, status=400)
        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket:
            return JsonResponse({'Status': False, 'Error': 'Корзина не найдена'}, status=404)
        updated_count = 0
        for item in items:
            if isinstance(item.get('id'), int) and isinstance(item.get('quantity'), int):
                updated_count += OrderItem.objects.filter(order=basket, id=item['id']).update(quantity=item['quantity'])
        return JsonResponse({'Status': True, 'Обновлено объектов': updated_count})


class AccountDetails(APIView):
    def get(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        if 'password' in request.data:
            try:
                validate_password(request.data['password'])
            except ValidationError as exc:
                return JsonResponse({'Status': False, 'Errors': {'password': exc.messages}})
            request.user.set_password(request.data['password'])
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': serializer.errors})


class PartnerState(APIView):
    def get(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=bool(strtobool(state)))
                return JsonResponse({'Status': True})
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerOrders(APIView):
    def get(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        orders = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    def get(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        contacts = Contact.objects.filter(user=request.user)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'city', 'street', 'phone'}.issubset(request.data):
            data = request.data.copy()
            data['user'] = request.user.id

            serializer = ContactSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def put(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        contact_id = request.data.get('id')
        if contact_id and str(contact_id).isdigit():
            contact = Contact.objects.filter(id=contact_id, user=request.user).first()
            if contact:
                serializer = ContactSerializer(contact, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def delete(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_str = request.data.get('items')
        if not items_str:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

        item_ids = [int(i) for i in items_str.split(',') if i.isdigit()]
        deleted_count, _ = Contact.objects.filter(user=request.user, id__in=item_ids).delete()
        return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})


class OrderView(APIView):
    def get(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        orders = Order.objects.filter(user=request.user).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request: Request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        if {'id', 'contact'}.issubset(request.data):
            order_id = request.data['id']
            contact_id = request.data['contact']
            if str(order_id).isdigit():
                try:
                    updated = Order.objects.filter(user=request.user, id=order_id).update(contact_id=contact_id, state='new')
                except IntegrityError:
                    return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'})
                if updated:
                    new_order.send(sender=self.__class__, user_id=request.user.id)
                    return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})
