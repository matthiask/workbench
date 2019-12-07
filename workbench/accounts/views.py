from django.conf import settings
from django.contrib import auth, messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import get_language, gettext as _
from django.views.decorators.cache import never_cache

from authlib.google import GoogleOAuth2Client

from workbench.accounts.forms import UserForm
from workbench.accounts.models import User
from workbench.awt.models import WorkingTimeModel
from workbench.generic import UpdateView


def accounts(request):
    return redirect("accounts_update" if request.user.is_authenticated else "login")


class UserUpdateView(UpdateView):
    model = User
    form_class = UserForm
    success_url = reverse_lazy("accounts_update")

    def get_object(self):
        return self.request.user


@never_cache
def login(request):
    if request.user.is_authenticated:
        return redirect("/")
    return render(request, "accounts/login.html")


@never_cache
def oauth2(request):
    client = GoogleOAuth2Client(
        request, login_hint=request.COOKIES.get("login_hint", "")
    )

    if not request.GET.get("code"):
        return redirect(client.get_authentication_url())

    try:
        user_data = client.get_user_data()
    except Exception:
        messages.error(request, _("Error while fetching user data. Please try again."))
        return redirect("login")

    email = user_data.get("email")
    new_user = False

    if email.endswith("@%s" % settings.WORKBENCH.SSO_DOMAIN):
        user, new_user = User.objects.get_or_create(
            email=email,
            defaults={
                "language": get_language(),
                "working_time_model": WorkingTimeModel.objects.first(),
            },
        )

    user = auth.authenticate(request, email=email)
    if user and user.is_active:
        auth.login(request, user)
    else:
        messages.error(request, _("No user with email address %s found.") % email)
        response = redirect("login")
        response.delete_cookie("login_hint")
        return response

    if new_user:
        messages.success(request, _("Welcome! Please fill in your details."))
        response = redirect("accounts_update")
        response.set_cookie("login_hint", user.email, expires=30 * 86400)
        return response

    next = request.get_signed_cookie("next", default=None, salt="next")
    response = redirect(next if next else "/")
    response.delete_cookie("next")
    response.set_cookie("login_hint", user.email, expires=30 * 86400)
    return response


def logout(request):
    auth.logout(request)
    messages.success(request, _("You have been signed out."))
    response = redirect("login")
    response.delete_cookie("login_hint")
    return response
