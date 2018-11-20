from django import http
from django.conf import settings
from django.contrib import auth, messages
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache

from oauth2client.client import OAuth2WebServerFlow, FlowExchangeError

from workbench import generic
from workbench.accounts.forms import UserForm
from workbench.accounts.models import User


def accounts(request):
    return http.HttpResponseRedirect(
        reverse("accounts_update")
        if request.user.is_authenticated
        else reverse("login")
    )


class UserUpdateView(generic.UpdateView):
    model = User
    form_class = UserForm
    success_url = "/"

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        elif "user_email" in self.request.session:
            return User(email=self.request.session["user_email"])
        else:
            raise http.Http404

    def form_valid(self, form):
        response = http.HttpResponseRedirect(self.get_success_url())
        self.object = form.save(commit=False)
        if self.object.pk:  # Existed already
            self.object.save()
            return response

        self.object.email = self.request.session.pop("user_email")
        self.object.save()
        auth.login(self.request, auth.authenticate(email=self.object.email))
        return response


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

        user = auth.authenticate(email=email)
        if user and user.is_active:
            auth.login(request, user)
        else:
            messages.info(
                request,
                _(
                    "No user with email address %s found,"
                    " do you want to create a new account?"
                )
                % email,
            )
            request.session["user_email"] = email
            return http.HttpResponseRedirect(reverse("accounts_update"))

    next = request.get_signed_cookie("next", default=None, salt="next")
    response = http.HttpResponseRedirect(next if next else "/")
    response.delete_cookie("next")
    return response


def logout(request):
    auth.logout(request)
    messages.success(request, _("You have been signed out."))
    return http.HttpResponseRedirect(reverse("login"))
