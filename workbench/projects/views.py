from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _

from workbench.projects.forms import ProjectAutocompleteForm
from workbench.projects.models import Project, Service


def select(request):
    form = ProjectAutocompleteForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        return JsonResponse(
            {"redirect": form.cleaned_data["project"].get_absolute_url()}, status=299
        )
    return render(
        request,
        "generic/select_object.html",
        {"form": form, "title": _("Jump to project")},
    )


def set_order(request):
    for index, id in enumerate(request.POST.getlist("ids[]")):
        Service.objects.filter(id=id).update(position=10 * (index + 1))
    return HttpResponse("OK", status=202)  # Accepted


def services(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return JsonResponse(
        {
            "id": project.id,
            "code": project.code,
            "title": project.title,
            "owned_by": project.owned_by.get_short_name(),
            "customer_id": project.customer_id,
            "services": [
                (service.id, str(service)) for service in project.services.logging()
            ],
        }
    )
