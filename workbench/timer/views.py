import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from corsheaders.middleware import CorsMiddleware

from workbench.timer.models import TimerState, Timestamp
from workbench.tools.forms import ModelForm


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


class TimestampForm(ModelForm):
    class Meta:
        model = Timestamp
        fields = ["type", "notes"]

    def save(self):
        instance = super().save(commit=False)
        instance.user = self.request.user
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
