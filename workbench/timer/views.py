import datetime as dt

from corsheaders.middleware import CorsMiddleware
from django import forms
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import decorator_from_middleware
from django.utils.timezone import make_aware
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

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


class TokenUserMixin:
    def clean(self):
        data = super().clean()
        if self.request.user.is_authenticated:
            data["user"] = self.request.user
        else:
            try:
                data["user"] = User.objects.get(
                    token=self.request.POST.get("token")
                    or self.request.GET.get("token")
                )
            except Exception as exc:
                raise forms.ValidationError("Invalid user") from exc
        return data


class TimestampForm(TokenUserMixin, ModelForm):
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


class TokenUserForm(TokenUserMixin, Form):
    pass


@decorator_from_middleware(CorsMiddleware)
@require_GET
def list_timestamps(request):
    form = TokenUserForm(request.GET, request=request)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.as_json()}, status=400)

    user = form.cleaned_data["user"]
    slices = Timestamp.objects.slices(user)
    daily_hours = sum(
        (slice["logged_hours"].hours for slice in slices if slice.get("logged_hours")),
        Z1,
    )

    return JsonResponse({
        "success": True,
        "user": str(user),
        "hours": daily_hours,
        "timestamps": [
            {
                "timestamp": "{:>5} - {:>5} {:^7} {}".format(
                    local_date_format(slice.get("starts_at"), fmt="H:i") or "?  ",
                    local_date_format(slice.get("ends_at"), fmt="H:i") or "?  ",
                    (
                        f"({hours(slice.elapsed_hours, plus_sign=True)})"
                        if slice.elapsed_hours is not None
                        else "?"
                    ),
                    slice["description"] or "-",
                ),
                "elapsed": slice.elapsed_hours,
                "comment": slice.get("comment", ""),
            }
            for slice in slices
        ],
    })


@require_POST
def delete_timestamp(request, pk):
    timestamp = get_object_or_404(Timestamp.objects.filter(user=request.user), pk=pk)
    timestamp.delete()
    messages.success(
        request,
        _("%(class)s '%(object)s' has been deleted successfully.")
        % {"class": timestamp._meta.verbose_name, "object": timestamp},
    )
    return HttpResponseRedirect(reverse("timestamps") + request.POST.get("next", ""))


class DayForm(Form):
    day = forms.DateField(required=False)


@filter_form(DayForm)
def timestamps(request, form):
    request.user.take_a_break_warning(request=request)
    request.user.unlogged_timestamps_warning(request=request)
    today = dt.date.today()
    day = form.cleaned_data["day"] or today

    # Calculate the start of the week (Monday) and the end of the week (today)
    week_start = today - dt.timedelta(days=today.weekday())
    week_end = today

    # Check if the displayed day is within the current week
    is_this_week = week_start <= day <= week_end

    # Fetch the timestamps for the selected day
    slices = Timestamp.objects.slices(request.user, day=day)

    # Calculate the logged hours for the day
    hours = sum(
        (slice["logged_hours"].hours for slice in slices if slice.get("logged_hours")),
        Z1,
    )

    # Loop through each day of the week (from Monday to the current day)
    weekly_hours = Z1
    for i in range(7):
        current_day = week_start + dt.timedelta(days=i)
        # Fetch the timestamps for the current day
        day_slices = Timestamp.objects.slices(request.user, day=current_day)

        # Sum the hours for the current day, if present
        daily_hours = sum(
            (
                slice["logged_hours"].hours
                for slice in day_slices
                if slice.get("logged_hours")
            ),
            Z1,
        )
        weekly_hours += daily_hours

    return render(
        request,
        "timestamps.html",
        {
            "slices": slices,
            "hours": hours,
            "weekly_hours": weekly_hours,
            "day": day,
            "previous": day - dt.timedelta(days=1),
            "next": day + dt.timedelta(days=1) if day < today else None,
            "url": request.build_absolute_uri(reverse("create_timestamp")),
            "is_today": day == today,
            "is_this_week": is_this_week,
        },
    )
