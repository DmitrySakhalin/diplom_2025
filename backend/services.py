import os
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import APIView
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from requests import get
from yaml import load as load_yaml, Loader

from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter


class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика.
    В случае отсутствия 'url' в запросе, данные загружаются из всех файлов в папке data/.
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if url:
            # Загрузка по URL (если указан)
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})

            try:
                stream = get(url).content
                data = load_yaml(stream, Loader=Loader)
            except Exception as e:
                return JsonResponse({'Status': False, 'Error': f'Ошибка загрузки или парсинга YAML: {str(e)}'})

            self._process_data(data, request.user)
            return JsonResponse({'Status': True})

        else:
            # Загрузка из локальных файлов в папке data/
            data_dir = os.path.join(settings.BASE_DIR, 'data')
            yaml_files = [f for f in os.listdir(data_dir) if f.endswith('.yaml') or f.endswith('.yml')]
            if not yaml_files:
                return JsonResponse({'Status': False, 'Errors': 'В папке data нет yaml файлов'}, status=400)

            for file_name in yaml_files:
                file_path = os.path.join(data_dir, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = load_yaml(f, Loader=Loader)
                        self._process_data(data, request.user)
                except Exception as e:
                    return JsonResponse({'Status': False, 'Error': f'Ошибка обработки файла {file_name}: {str(e)}'}, status=400)

            return JsonResponse({'Status': True})

    def _process_data(self, data, user):
        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user.id)

        for category in data['categories']:
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
