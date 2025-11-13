from rollbar.contrib.django.middleware import RollbarNotifierMiddleware

class CustomRollbarNotifierMiddleware(RollbarNotifierMiddleware):
    def get_extra_data(self, request, exc):
        # Дополнительные метаданные для ошибки (необязательно)
        extra_data = {
            'trace_id': 'aabbccddeeff',
            'feature_flags': [
                'feature_1',
                'feature_2',
            ]
        }
        return extra_data

    def get_payload_data(self, request, exc):
        payload_data = {}
        if not request.user.is_anonymous:
            # Информация о пользователе (id обязательное поле)
            payload_data = {
                'person': {
                    'id': request.user.id,
                    'username': request.user.username,
                    'email': request.user.email,
                },
            }
        return payload_data
