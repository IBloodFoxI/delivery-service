from django.contrib.auth.backends import ModelBackend
from .crypto import make_hash


class PhoneAuthBackend(ModelBackend):
    """Аутентификация по номеру телефона через HMAC-хэш."""

    def authenticate(self, request, username=None, password=None, phone_number=None, **kwargs):
        from .models import User

        raw_phone = phone_number or username
        if not raw_phone:
            return None

        phone_h = make_hash(raw_phone)
        try:
            user = User.objects.get(phone_hash=phone_h)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        from .models import User
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
