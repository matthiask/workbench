from django.conf import settings
from django.contrib import messages
from django.db import connections
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import activate, gettext as _


def set_user_name(username):
    connections["default"].cursor().execute(
        "SET SESSION application_name TO %s", [username]
    )


def user_middleware(get_response):
    def middleware(request):
        if request.user.is_authenticated:
            set_user_name(
                "user-%d-%s" % (request.user.id, request.user.get_short_name())
            )
            activate(request.user.language)
            return get_response(request)

        set_user_name("user-0-anonymous")

        if request.path.startswith(settings.LOGIN_REQUIRED_EXEMPT):
            return get_response(request)

        messages.info(request, _("Please authenticate."))

        response = HttpResponseRedirect(reverse("login"))
        response.set_signed_cookie("next", request.get_full_path(), salt="next")
        return response

    return middleware
