from yaml import load as load_yaml, Loader
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter


def load_products_from_yaml(file_path, user):
    """
    Функция загрузки товаров из YAML файла.
    file_path: полный путь к YAML файлу
    user: пользователь (Postavshhik), для связи с магазином
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = load_yaml(f, Loader=Loader)

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
