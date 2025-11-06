from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django import forms

from backend.models import (
    User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
    Order, OrderItem, Contact, ConfirmEmailToken
)
from backend.services import load_products_from_yaml
import os
from django.conf import settings


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company', 'position')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'type', 'is_staff', 'is_active')
    list_filter = ('type', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ('product_info', 'quantity')
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'state', 'dt', 'total_price')
    readonly_fields = ('total_price',)
    inlines = [OrderItemInline]

    def save_formset(self, request, form, formset, change):
        formset.save()

        order = form.instance
        total = order.calculate_total_price()

        if order.total_price != total:
            order.total_price = total
            order.save(update_fields=['total_price'])


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
    list_display = ('id', 'name', 'category', 'get_price')
    list_filter = ('category',)
    search_fields = ('name',)

    def get_price(self, obj):
        prices = obj.product_infos.values_list('price', flat=True)
        if prices:
            return min(prices)
        return '-'
    get_price.short_description = 'Цена'


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'shop', 'price', 'quantity')
    list_filter = ('shop', 'product__category')
    search_fields = ('product__name',)

    def __str__(self):
        return f"{self.product.name} ({self.shop.name}) - {self.price} руб."


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


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product_info', 'quantity']

class OrderItemInline(admin.TabularInline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i, form in enumerate(self.forms):
            if not form.instance.pk:
                if self.instance.pk is None and i == 0:
                    form.initial['quantity'] = 0
                else:
                    form.initial['quantity'] = 1


class OrderItemInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i, form in enumerate(self.forms):
            if not form.instance.pk:
                if self.instance.pk is None and i == 0:
                    form.initial['quantity'] = 0
                else:
                    form.initial['quantity'] = 1

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    formset = OrderItemInlineFormSet
    fields = ('product_info', 'quantity')
    extra = 1

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
