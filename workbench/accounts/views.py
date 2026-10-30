import re

from authlib.google import GoogleOAuth2Client
from django.conf import settings
from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.cache import never_cache

from workbench.accounts.forms import UserForm
from workbench.accounts.models import API_TOKEN_LIFETIME, APIToken, User
from workbench.accounts.reporting import logged_hours
from workbench.generic import DetailView, UpdateView
from workbench.projects.models import Project
from workbench.tools.charts import bar_chart
from workbench.tools.formats import hours


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
        if "user_email" in self.request.session:
            email = self.request.session["user_email"]
            return User(email=email, _short_name=email.split("@")[0])
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
    if (
        settings.DEBUG
        and not settings.LIVE
        and (email := request.GET.get("force_login"))
    ):
        user = auth.authenticate(request, email=email)
        if user:
            auth.login(request, user)
            return redirect("/")
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
    except Exception:  # noqa: BLE001
        messages.error(request, _("Error while fetching user data. Please try again."))
        return redirect("login")

    email = user_data.get("email")
    user = auth.authenticate(request, email=email)
    if user and user.is_active:
        auth.login(request, user)
        next = request.get_signed_cookie("next", default=None, salt="next")
        response = redirect(next or "/")
        response.delete_cookie("next")
        response.set_cookie("login_hint", user.email, expires=180 * 86400)
        return response

    if User.objects.filter(email=email).exists():
        messages.error(
            request, _("The user with email address %s is inactive.") % email
        )
        response = HttpResponseRedirect("{}?error=1".format(reverse("login")))
        response.delete_cookie("login_hint")
        return response

    if email.endswith("@%s" % settings.WORKBENCH.SSO_DOMAIN):
        messages.info(request, _("Welcome! Please fill in your details."))
        request.session["user_email"] = email
        return redirect("accounts_update")

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
    template_name_suffix = "_statistics"

    def get_context_data(self, **kwargs):
        stats = logged_hours(self.object)
        weeks = stats["hours_per_week"]
        labels = [f"KW{row['week']:%V}" for row in weeks]
        expected = {
            "label": _("Expected"),
            "values": [row["expected_hours"] for row in weeks],
            "color": "wb-series-muted",
            "dashed": True,
        }
        return super().get_context_data(
            logged_hours=stats,
            hours_per_week_chart=bar_chart(
                labels,
                bars=[
                    {
                        "label": label,
                        "values": [row["by_type"].get(type, 0) for row in weeks],
                        "color": f"wb-series-{index}",
                    }
                    for index, (type, label) in enumerate(Project.TYPE_CHOICES, 1)
                ],
                lines=[expected],
                fmt=hours,
            ),
            hours_per_customer_chart=bar_chart(
                labels,
                bars=[
                    {
                        "label": row["name"],
                        "values": row["hours"],
                        "color": f"wb-series-{index}",
                    }
                    for index, row in enumerate(
                        stats["hours_per_customer"]["by_customer"], 1
                    )
                ],
                lines=[expected],
                fmt=hours,
                height=360,
            ),
            **kwargs,
        )


def pin(request, pk, *, model, attribute):
    instance = get_object_or_404(model, pk=pk)
    manager = getattr(request.user, attribute)
    if request.GET.get("pinned"):
        manager.add(instance)
        return JsonResponse({"pinned": True})
    manager.remove(instance)
    return JsonResponse({"pinned": False})


@never_cache
@login_required
def api_tokens(request):
    secret = None
    if request.method == "POST":
        if pk := request.POST.get("delete"):
            request.user.api_tokens.filter(pk=pk).delete()
            messages.success(request, _("The API token has been deleted."))
            return redirect("accounts_api_tokens")
        title = request.POST.get("title", "").strip()
        access = request.POST.get("access")
        if title and access in APIToken.Access.values:
            _token, secret = APIToken.create_for(
                user=request.user, title=title[:100], access=access
            )

    return render(
        request,
        "accounts/api_tokens.html",
        {
            "tokens": request.user.api_tokens.all(),
            "secret": secret,
            "days": API_TOKEN_LIFETIME.days,
            "access_choices": APIToken.Access.choices,
        },
    )


@never_cache
def cli_login(request):
    """Authorize the wb CLI on this computer

    The CLI waits on a local port for the token. The login middleware makes
    sure that the user is authenticated."""
    try:
        port = int(request.GET["port"])
    except KeyError, ValueError:
        port = 0
    state = request.GET.get("state", "")
    if not 1024 <= port <= 65535 or not re.fullmatch(r"[\w-]{16,100}", state):
        return HttpResponseBadRequest("Invalid port or state.")
    # wb has to ask for the access explicitly
    if (access := request.GET.get("access")) not in APIToken.Access.values:
        return HttpResponseBadRequest(
            "Invalid access. Upgrade wb and run wb login --read or --write."
        )
    name = request.GET.get("name", "")[:50]

    if request.method == "POST":
        _token, secret = APIToken.create_for(
            user=request.user,
            title=f"wb ({name})" if name else "wb",
            access=access,
        )
        return render(
            request,
            "accounts/cli_login_redirect.html",
            {"action": f"http://127.0.0.1:{port}/", "token": secret, "state": state},
        )

    return render(
        request,
        "accounts/cli_login.html",
        {
            "name": name,
            "days": API_TOKEN_LIFETIME.days,
            "access": APIToken.Access(access),
        },
    )
