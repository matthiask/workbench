import datetime as dt

from django import forms
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import decorator_from_middleware
from django.utils.timezone import make_aware
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from corsheaders.middleware import CorsMiddleware

from workbench.accounts.models import User
from workbench.timer.models import Timestamp
from workbench.tools.formats import Z1, hours, local_date_format
from workbench.tools.forms import Form, ModelForm
from workbench.tools.validation import filter_form


def timer(request):
    return render(
        request,
        "timer.html",
        {
            "hours": {
                "today": hours(request.user.hours["today"]),
                "week": hours(request.user.hours["week"]),
            },
        },
    )


class SignedEmailUserMixin:
    def clean(self):
        data = super().clean()
        if self.request.user.is_authenticated:
            data["user"] = self.request.user
        else:
            try:
                data["user"] = User.objects.get_by_signed_email(
                    self.request.POST.get("user") or self.request.GET.get("user")
                )
            except Exception:
                raise forms.ValidationError("Invalid user")
        return data


class TimestampForm(SignedEmailUserMixin, ModelForm):
    time = forms.TimeField(required=False)

    class Meta:
        model = Timestamp
        fields = ["type", "notes"]

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data["type"] = "stop" if data.get("type") == "split" else data.get("type")
        super().__init__(data, *args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get("time"):
            data["created_at"] = make_aware(
                dt.datetime.combine(dt.date.today(), data["time"])
            )
        return data

    def save(self):
        instance = super().save(commit=False)
        instance.created_at = self.cleaned_data.get("created_at", instance.created_at)
        instance.user = self.cleaned_data["user"]
        instance.save()
        return instance


@csrf_exempt
@decorator_from_middleware(CorsMiddleware)
@require_POST
def create_timestamp(request):
    form = TimestampForm(request.POST, request=request)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.as_json()}, status=400)
    return JsonResponse({"success": str(form.save())}, status=201)


class SignedEmailUserForm(SignedEmailUserMixin, Form):
    pass


@decorator_from_middleware(CorsMiddleware)
@require_GET
def list_timestamps(request):
    form = SignedEmailUserForm(request.GET, request=request)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.as_json()}, status=400)

    user = form.cleaned_data["user"]
    slices = Timestamp.objects.slices(user)
    daily_hours = sum(
        (slice["logged_hours"].hours for slice in slices if slice.get("logged_hours")),
        Z1,
    )
    return JsonResponse(
        {
            "success": True,
            "user": str(user),
            "hours": daily_hours,
            "timestamps": [
                {
                    "timestamp": "{:>5} - {:>5} {:^7} {}".format(
                        local_date_format(slice.get("starts_at"), fmt="H:i") or "?  ",
                        local_date_format(slice.get("ends_at"), fmt="H:i") or "?  ",
                        "({})".format(hours(slice.elapsed_hours, plus_sign=True))
                        if slice.elapsed_hours is not None
                        else "?",
                        slice["description"] or "-",
                    ),
                    "elapsed": slice.elapsed_hours,
                    "comment": slice.get("comment", ""),
                }
                for slice in slices
            ],
        }
    )


@require_POST
def delete_timestamp(request, pk):
    timestamp = get_object_or_404(Timestamp.objects.filter(user=request.user), pk=pk)
    timestamp.delete()
    messages.success(
        request,
        _("%(class)s '%(object)s' has been deleted successfully.")
        % {"class": timestamp._meta.verbose_name, "object": timestamp},
    )
    return redirect("timestamps")


class DayForm(Form):
    day = forms.DateField(required=False)


@filter_form(DayForm)
def timestamps(request, form):
    request.user.take_a_break_warning(request=request)
    today = dt.date.today()
    day = form.cleaned_data["day"] or today
    slices = Timestamp.objects.slices(request.user, day=day)
    hours = sum(
        (slice["logged_hours"].hours for slice in slices if slice.get("logged_hours")),
        Z1,
    )
    return render(
        request,
        "timestamps.html",
        {
            "slices": slices,
            "hours": hours,
            "day": day,
            "previous": day - dt.timedelta(days=1),
            "next": day + dt.timedelta(days=1) if day < today else None,
            "url": request.build_absolute_uri(reverse("create_timestamp")),
            "is_today": day == today,
        },
    )
