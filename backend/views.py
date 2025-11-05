from rest_framework.views import APIView
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from requests import get
from yaml import load as load_yaml, Loader
from backend.models import Shop, Category, ProductInfo, Parameter, ProductParameter, Product
from backend.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, OrderItemSerializer, OrderSerializer, ContactSerializer
from backend.services import load_products_from_yaml


class PartnerUpdate(APIView):
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')

        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})

            try:
                stream = get(url).content
                data = load_yaml(stream, Loader=Loader)
            except Exception as e:
                return JsonResponse({'Status': False, 'Error': f'Error fetching or parsing YAML: {str(e)}'})

            # Используем сервис для обработки данных
            load_products_from_yaml_from_data(data, request.user)
            return JsonResponse({'Status': True})

        else:
            # Загрузка из локальных файлов (например, из папки data), тут можно вызвать функцию в цикле
            import os
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
    # Вспомогательная функция для загрузки из данных (не из файла)
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
