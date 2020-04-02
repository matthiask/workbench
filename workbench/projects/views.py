from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from workbench import generic
from workbench.projects.forms import OffersRenumberForm, ProjectAutocompleteForm
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType
from workbench.templatetags.workbench import h


def select(request):
    if not request.is_ajax():
        return redirect("/")
    form = ProjectAutocompleteForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        data = form.cleaned_data
        return JsonResponse(
            {
                "redirect": data["service"].get_absolute_url()
                if data["service"]
                else data["project"].get_absolute_url()
            },
            status=299,
        )
    return render(
        request,
        "generic/select_object.html",
        {
            "form": form,
            "title": _("Jump to project"),
            "links": [
                {"title": h(project), "url": project.get_absolute_url(), "attrs": ""}
                for project in request.user.active_projects
            ],
        },
    )


class OffersRenumberView(generic.UpdateView):
    form_class = OffersRenumberForm


def assign_service_type(request, pk):
    service = Service.objects.get(pk=pk)
    service_type = ServiceType.objects.get(pk=request.GET.get("service_type"))

    service.effort_type = service_type.title
    service.effort_rate = service_type.hourly_rate
    service.save()
    messages.success(
        request,
        _("%(class)s '%(object)s' has been updated successfully.")
        % {"class": service._meta.verbose_name, "object": service},
    )
    return redirect(service)


def set_order(request):
    for index, id in enumerate(request.POST.getlist("ids[]")):
        Service.objects.filter(id=id).update(position=10 * (index + 1))
    return HttpResponse("OK", status=202)  # Accepted


def services(request, pk):
    project = get_object_or_404(Project, pk=pk)
    offers = {None: {"label": _("Not offered yet"), "options": []}}
    for service in project.services.logging().select_related("offer__owned_by"):
        if service.offer not in offers:
            offers[service.offer] = {"label": str(service.offer), "options": []}
        offers[service.offer]["options"].append(
            {"label": str(service), "value": service.id}
        )

    return JsonResponse(
        {
            "id": project.id,
            "code": project.code,
            "title": project.title,
            "owned_by": project.owned_by.get_short_name(),
            "customer_id": project.customer_id,
            "services": [
                data for offer, data in sorted(offers.items()) if data["options"]
            ],
        }
    )


def projects(request):
    return JsonResponse(
        {
            "projects": [
                {"label": str(project), "value": project.pk}
                for project in request.user.active_projects
            ],
        }
    )
