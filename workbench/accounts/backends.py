from workbench.accounts.models import User


class AuthBackend:
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def authenticate(self, request, **kwargs):
        try:
            return User.objects.get(email=kwargs.get("email"))
        except User.DoesNotExist:
            pass
