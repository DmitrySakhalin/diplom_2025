from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
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

from backend.models import (Shop, Category, ProductInfo, Parameter, ProductParameter, Order, OrderItem, Contact,
                            ConfirmEmailToken, Product)
from backend.serializers import (
    UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer,
    OrderItemSerializer, OrderSerializer, ContactSerializer, OrderConfirmSerializer
)
from backend.signals import new_user_registered, new_order
from backend.services import load_products_from_yaml_from_data


class RegisterAccount(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request):
        required_fields = {'first_name', 'last_name', 'email', 'password', 'company', 'position'}
        if not required_fields.issubset(request.data):
            return Response(
                {'Status': False, 'Errors': 'Не указаны все необходимые аргументы'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_password(request.data['password'])
        except ValidationError as exc:
            return Response({'Status': False, 'Errors': {'password': exc.messages}})

        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.set_password(request.data['password'])
            user.save()
            new_user_registered.send(sender=self.__class__, user_id=user.id)
            return Response({'Status': True})

        return Response({'Status': False, 'Errors': serializer.errors})


class LoginAccount(APIView):
    def post(self, request):
        if not {'email', 'password'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})
        user = authenticate(request=request, username=request.data['email'], password=request.data['password'])
        if user is not None and user.is_active:
            token, _ = Token.objects.get_or_create(user=user)
            return JsonResponse({'Status': True, 'Token': token.key})
        return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})


class PartnerUpdate(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')

        if url:
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

            load_products_from_yaml_from_data(data, request.user)
            return JsonResponse({'Status': True})

        else:
            import os
            from django.conf import settings
            data_dir = os.path.join(settings.BASE_DIR, 'data')
            yaml_files = [f for f in os.listdir(data_dir) if f.endswith('.yaml') or f.endswith('.yml')]
            if not yaml_files:
                return JsonResponse({'Status': False, 'Errors': 'В папке data нет yaml файлов'}, status=400)

            for file_name in yaml_files:
                file_path = os.path.join(data_dir, file_name)
                try:
                    load_products_from_yaml(file_path, request.user)
                except Exception as e:
                    return JsonResponse({'Status': False, 'Error': f'Ошибка обработки файла {file_name}: {str(e)}'}, status=400)

            return JsonResponse({'Status': True})


def load_products_from_yaml_from_data(data, user):
    shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user.id)

    for category in data.get('categories', []):
        category_obj, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
        category_obj.shops.add(shop)
        category_obj.save()

    ProductInfo.objects.filter(shop=shop).delete()

    for item in data.get('goods', []):
        product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

        product_info = ProductInfo.objects.create(
            product=product,
            external_id=item['id'],
            model=item.get('model', ''),
            price=item['price'],
            price_rrc=item['price_rrc'],
            quantity=item['quantity'],
            shop=shop
        )

        for name, value in item.get('parameters', {}).items():
            param_obj, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.create(product_info=product_info, parameter=param_obj, value=value)


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
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
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

    def post(self, request):
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

    def delete(self, request):
        items_str = request.data.get('items')
        if not items_str:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

        item_ids = [int(i) for i in items_str.split(',') if i.isdigit()]
        basket = Order.objects.filter(user=request.user, state='basket').first()

        if not basket:
            return JsonResponse({'Status': False, 'Error': 'Корзина не найдена'}, status=404)

        deleted_count, _ = OrderItem.objects.filter(order=basket, id__in=item_ids).delete()
        return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

    def put(self, request):
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
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request: Request):
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
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request: Request):
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
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
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
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        contacts = Contact.objects.filter(user=request.user)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request: Request):
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
        items_str = request.data.get('items')
        if not items_str:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

        item_ids = [int(i) for i in items_str.split(',') if i.isdigit()]
        deleted_count, _ = Contact.objects.filter(user=request.user, id__in=item_ids).delete()
        return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})


class OrderView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        orders = Order.objects.filter(user=request.user).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = OrderConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # вызывает ValidationError и возвращает 400, если данные некорректны

        order_id = serializer.validated_data['id']
        contact_id = serializer.validated_data['contact']

        updated = Order.objects.filter(user=request.user, id=order_id).update(contact_id=contact_id, state='new')
        if updated:
            new_order.send(sender=self.__class__, user_id=request.user.id)
            return Response({'Status': True})
        return Response({'Status': False, 'Errors': 'Заказ не найден или не изменён'}, status=400)