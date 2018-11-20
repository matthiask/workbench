from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache

from oauth2client.client import OAuth2WebServerFlow, FlowExchangeError

from workbench.accounts.forms import UserForm
from workbench.accounts.models import User
from workbench.generic import UpdateView


def accounts(request):
    return http.HttpResponseRedirect(
        reverse("accounts_update")
        if request.user.is_authenticated
        else reverse("login")
    )


class UserUpdateView(UpdateView):
    model = User
    form_class = UserForm
    success_url = reverse_lazy("accounts_update")

    def get_object(self):
        return self.request.user


def oauth2_flow(request):
    flow_kwargs = {
        "client_id": settings.OAUTH2_CLIENT_ID,
        "client_secret": settings.OAUTH2_CLIENT_SECRET,
        "scope": "email",
        "access_type": "online",  # Should be the default...
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://accounts.google.com/o/oauth2/token",
        "revoke_uri": "https://accounts.google.com/o/oauth2/revoke",
        "redirect_uri": request.build_absolute_uri(reverse("accounts_oauth2")),
    }

    return OAuth2WebServerFlow(**flow_kwargs)


@never_cache
def login(request):
    if request.user.is_authenticated:
        return http.HttpResponseRedirect("/")
    return render(request, "accounts/login.html")


@never_cache
def oauth2(request):
    flow = oauth2_flow(request)

    code = request.GET.get("code")
    if not code:
        return http.HttpResponseRedirect(flow.step1_get_authorize_url())

    try:
        credentials = flow.step2_exchange(code)
    except FlowExchangeError:
        messages.error(request, _("OAuth2 error: Credential exchange failed"))
        return http.HttpResponseRedirect("/")

    if credentials.id_token["email_verified"]:
        email = credentials.id_token["email"]

        _u, created = User.objects.get_or_create(
            email=email,
            defaults={
                "is_active": True,
                "is_admin": False,
                "_short_name": "",
                "_full_name": "",
            },
        )
        if created:
            messages.success(request, _("Welcome! Please fill in your details."))

        user = authenticate(email=email)
        if user and user.is_active:
            auth_login(request, user)
        else:
            messages.error(request, _("No user with email address %s found.") % email)

        if created:
            return http.HttpResponseRedirect(reverse("accounts_update"))

    next = request.get_signed_cookie("next", default=None, salt="next")
    response = http.HttpResponseRedirect(next if next else "/")
    response.delete_cookie("next")
    return response


def logout(request):
    auth_logout(request)
    messages.success(request, _("You have been signed out."))
    return http.HttpResponseRedirect(reverse("login"))
