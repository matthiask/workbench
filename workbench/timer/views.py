import datetime as dt
import json

from django import forms
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from corsheaders.middleware import CorsMiddleware

from workbench.accounts.models import User
from workbench.timer.models import TimerState, Timestamp
from workbench.tools.formats import hours
from workbench.tools.forms import Form, ModelForm
from workbench.tools.validation import filter_form


def timer(request):
    if request.method == "POST":
        try:
            state = json.loads(request.POST.get("state"))
        except Exception:
            return JsonResponse({}, status=400)

        instance, created = TimerState.objects.update_or_create(
            user=request.user, defaults={"state": state}
        )
        return JsonResponse(
            {"success": True, "updated_at": instance.updated_at}, status=200
        )

    state = TimerState.objects.filter(user=request.user).first()
    return render(
        request,
        "timer.html",
        {
            "state": state.state if state else None,
            "hours": {
                "today": hours(request.user.hours["today"]),
                "week": hours(request.user.hours["week"]),
            },
        },
    )


class TimestampForm(ModelForm):
    time = forms.TimeField(required=False)

    class Meta:
        model = Timestamp
        fields = ["type", "notes"]

    def clean(self):
        data = super().clean()
        if self.request.user.is_authenticated:
            data["user"] = self.request.user
        else:
            try:
                data["user"] = User.objects.get_by_signed_email(
                    self.request.POST.get("user")
                )
            except Exception:
                raise forms.ValidationError("Invalid user")
        return data

    def save(self):
        instance = super().save(commit=False)
        instance.user = self.cleaned_data["user"]
        instance.save()
        return instance


@csrf_exempt
@decorator_from_middleware(CorsMiddleware)
@require_POST
def create_timestamp(request):
    form = TimestampForm(request.POST, request=request)
    if not form.is_valid():
        return JsonResponse({}, status=400)
    form.save()
    return JsonResponse({}, status=201)


class DayForm(Form):
    day = forms.DateField(required=False)


@filter_form(DayForm)
def timestamps(request, form):
    request.user.take_a_break_warning(request=request)
    today = dt.date.today()
    day = form.cleaned_data["day"] or today
    timestamps = Timestamp.objects.for_user(request.user, day=day)
    return render(
        request,
        "timestamps.html",
        {
            "timestamps": timestamps,
            "day": day,
            "previous": day - dt.timedelta(days=1),
            "next": day + dt.timedelta(days=1) if day < today else None,
            "url": request.build_absolute_uri(reverse("create_timestamp")),
            "is_today": day == today,
            "hours": hours,
        },
    )
