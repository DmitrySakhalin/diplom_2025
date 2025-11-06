# API-сервиса для магазина

Краткое описание проекта: 
Дипломный проект с API на Django REST Framework с автоматической документацией через drf-spectacular. 



## Требования

- Python 3.10+
- Django 5.2+
- др. зависимости указаны в requirements.txt

## Установка и запуск

1. Клонируйте репозиторий: ```git clone https://github.com/DmitrySakhalin/diplom_2025.git```
2. Работаем с папки: ```cd netology_pd_diplom```
3. Создайте и активируйте виртуальное окружение: ```source venv/bin/activate```
4. Установите зависимости: ```pip install -r requirements.txt ```
5. Выполните миграции базы данных: ```python manage.py migrate```
6. (Опционально) Создайте суперпользователя для доступа в админку:```python manage.py createsuperuser``` 
7. Запустите сервер разработки: ```python manage.py runserver```

---

Документация API доступна по адресу: 
```http://127.0.0.1:8000/api/api/docs/```

---








