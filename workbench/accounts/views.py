from django.conf import settings
from django.contrib import auth, messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.cache import never_cache

from authlib.google import GoogleOAuth2Client

from workbench.accounts.forms import UserForm
from workbench.accounts.models import User
from workbench.accounts.reporting import logged_hours
from workbench.generic import DetailView, UpdateView


def accounts(request):
    return redirect("accounts_update" if request.user.is_authenticated else "login")


class UserUpdateView(UpdateView):
    model = User
    form_class = UserForm
    success_url = "/"
    title = gettext_lazy("Settings")

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        elif "user_email" in self.request.session:
            email = self.request.session["user_email"]
            return User(email=email, _short_name=email.split("@")[0])
        else:
            raise Http404

    def form_valid(self, form):
        response = HttpResponseRedirect(self.get_success_url())
        self.object = form.save(commit=False)
        if self.object.pk:  # Existed already
            self.object.save()
            return response

        self.object.email = self.request.session.pop("user_email")
        self.object.save()
        auth.login(self.request, auth.authenticate(email=self.object.email))
        response.set_cookie("login_hint", self.object.email, expires=180 * 86400)
        return response


@never_cache
def login(request):
    if request.user.is_authenticated:
        return redirect("/")
    return render(
        request,
        "accounts/login.html",
        {
            "auth_params": "?login_hint=&prompt=consent+select_account",
            "auth_button": _("Select Google account"),
        }
        if request.GET.get("error")
        else {},
    )


@never_cache
def oauth2(request):
    auth_params = request.GET.dict()
    auth_params.setdefault("login_hint", request.COOKIES.get("login_hint", ""))
    client = GoogleOAuth2Client(request, authorization_params=auth_params)

    if not request.GET.get("code"):
        return redirect(client.get_authentication_url())

    try:
        user_data = client.get_user_data()
    except Exception:
        messages.error(request, _("Error while fetching user data. Please try again."))
        return redirect("login")

    email = user_data.get("email")
    user = auth.authenticate(request, email=email)
    if user and user.is_active:
        auth.login(request, user)
        next = request.get_signed_cookie("next", default=None, salt="next")
        response = redirect(next if next else "/")
        response.delete_cookie("next")
        response.set_cookie("login_hint", user.email, expires=180 * 86400)
        return response

    elif User.objects.filter(email=email).exists():
        messages.error(
            request, _("The user with email address %s is inactive.") % email
        )
        response = HttpResponseRedirect("{}?error=1".format(reverse("login")))
        response.delete_cookie("login_hint")
        return response

    elif email.endswith("@%s" % settings.WORKBENCH.SSO_DOMAIN):
        messages.info(request, _("Welcome! Please fill in your details."))
        request.session["user_email"] = email
        return redirect("accounts_update")

    else:
        messages.error(request, _("No user with email address %s found.") % email)
        response = HttpResponseRedirect("{}?error=1".format(reverse("login")))
        response.delete_cookie("login_hint")
        return response


def logout(request):
    auth.logout(request)
    messages.success(request, _("You have been signed out."))
    response = redirect("login")
    response.delete_cookie("login_hint")
    return response


class ProfileView(DetailView):
    model = User
    queryset = User.objects.active()
    template_name_suffix = "_statistics"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            logged_hours=logged_hours(self.object), **kwargs
        )
