from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url


class LoginRequiredMiddleware(object):
    def process_request(self, request):
        if request.path.startswith(('/admin/', '/accounts/')):
            return
        if request.user.is_authenticated():
            return

        return redirect_to_login(
            request.get_full_path(),
            resolve_url(settings.LOGIN_URL),
            REDIRECT_FIELD_NAME)
