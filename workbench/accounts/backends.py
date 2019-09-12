from workbench.accounts.models import User


class AuthBackend:
    def get_user(self, user_id):
        return User.objects.filter(pk=user_id).first()

    def authenticate(self, request, **kwargs):
        # Fine since email is unique
        return User.objects.filter(email=kwargs.get("email")).first()
