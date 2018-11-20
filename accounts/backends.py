from accounts.models import User


class AuthBackend(object):
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def authenticate(self, **kwargs):
        try:
            return User.objects.get(email=kwargs.get("email"))
        except User.DoesNotExist:
            pass
