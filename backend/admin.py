from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages

from backend.models import (
    User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
    Order, OrderItem, Contact, ConfirmEmailToken,
)
from backend.services import load_products_from_yaml
import os
from django.conf import settings


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Панель управления пользователями
    """
    model = User

    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company', 'position')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'type', 'is_staff', 'is_active')
    list_filter = ('type', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'state', 'import_price_button')
    list_filter = ('state',)
    search_fields = ('name', 'user__email')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-price/<int:shop_id>/', self.admin_site.admin_view(self.import_price), name='shop-import-price'),
        ]
        return custom_urls + urls

    def import_price_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Импорт прайса</a>',
            f'./import-price/{obj.pk}/'
        )
    import_price_button.short_description = 'Импорт прайса'
    import_price_button.allow_tags = True

    def import_price(self, request, shop_id):
        shop = self.get_object(request, shop_id)
        if not shop:
            self.message_user(request, "Магазин не найден", level=messages.ERROR)
            return redirect('..')

        file_path = os.path.join(settings.BASE_DIR, 'data', 'shop1.yaml')
        try:
            load_products_from_yaml(file_path, shop.user)
            self.message_user(request, f"Прайс для магазина {shop.name} успешно импортирован", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Ошибка импорта: {e}", level=messages.ERROR)
        return redirect('..')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'shop', 'price', 'quantity')
    list_filter = ('shop', 'product__category')
    search_fields = ('product__name',)


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 0


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ('product_info', 'parameter', 'value')
    search_fields = ('parameter__name',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_info', 'quantity')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'state', 'dt', 'total_price')
    list_filter = ('state', 'dt')
    search_fields = ('user__email',)
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_info', 'quantity')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'street', 'house', 'phone')
    search_fields = ('user__email', 'city', 'phone')


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at')
    search_fields = ('user__email',)
