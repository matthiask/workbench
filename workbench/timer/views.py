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
    return render(request, "timer.html", {"state": state.state if state else None})


class TimestampForm(forms.ModelForm):
    user = forms.CharField(required=False)

    class Meta:
        model = Timestamp
        fields = ["type", "notes"]


@csrf_exempt
@decorator_from_middleware(CorsMiddleware)
@require_POST
def create_timestamp(request):
    form = TimestampForm(request.POST)
    if not form.is_valid():
        return JsonResponse({}, status=400)
    instance = form.save(commit=False)
    if request.user.is_authenticated:
        instance.user = request.user
    elif form.cleaned_data.get("user"):
        try:
            instance.user = User.objects.get_by_signed_email(form.cleaned_data["user"])
        except Exception:
            return JsonResponse({}, status=403)
    else:
        return JsonResponse({}, status=403)
    instance.save()
    return JsonResponse({}, status=201)


def timestamps(request):
    day = dt.date.today()
    return render(
        request,
        "timestamps.html",
        {
            "timestamps": Timestamp.for_user(request.user, day=day),
            "url": request.build_absolute_uri(reverse("create_timestamp")),
        },
    )
