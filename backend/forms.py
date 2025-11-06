from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

class LoginForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

class RegisterForm(forms.Form):
    last_name = forms.CharField(label='Фамилия', max_length=150)
    first_name = forms.CharField(label='Имя', max_length=150)
    email = forms.EmailField(label='Email', max_length=254)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким Email уже существует')
        return email

class ContactForm(forms.Form):
    last_name = forms.CharField(label='Фамилия', max_length=150)
    first_name = forms.CharField(label='Имя', max_length=150)
    middle_name = forms.CharField(label='Отчество', max_length=150, required=False)
    email = forms.EmailField(label='Email', max_length=254)
    phone = forms.CharField(label='Телефон', max_length=20)
    address = forms.CharField(label='Адрес', max_length=255)
    city = forms.CharField(label='Город', max_length=150)
    street = forms.CharField(label='Улица', max_length=150)
    house = forms.CharField(label='Дом', max_length=20)
    building = forms.CharField(label='Корпус', max_length=20, required=False)
    structure = forms.CharField(label='Строение', max_length=20, required=False)
    apartment = forms.CharField(label='Квартира', max_length=20, required=False)

class OrderConfirmForm(forms.Form):
    basket_id = forms.IntegerField(label='ID корзины')
    contact_id = forms.IntegerField(label='ID контакта')

