from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from workbench.projects.forms import ProjectAutocompleteForm
from workbench.projects.models import Service


def select(request):
    form = ProjectAutocompleteForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        return JsonResponse(
            {"redirect": form.cleaned_data["project"].get_absolute_url()}, status=299
        )
    return render(request, "projects/select_project.html", {"form": form})


def set_order(request):
    for index, id in enumerate(request.POST.getlist("ids[]")):
        Service.objects.filter(id=id).update(position=10 * (index + 1))
    return HttpResponse("OK", status=202)  # Accepted
