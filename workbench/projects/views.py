from collections import defaultdict

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from xlsxdocument import XLSXDocument

from workbench import generic
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.forms import OffersRenumberForm, ProjectAutocompleteForm
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType
from workbench.templatetags.workbench import h
from workbench.tools.formats import Z2, local_date_format


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
                {
                    "title": h(project),
                    "url": project.get_absolute_url(),
                    "attrs": "",
                    "shortcut": (idx + 1) % 10 if idx < 10 else None,
                    "is_pinned": getattr(project, "is_pinned", False),
                }
                for idx, project in enumerate(request.user.active_projects)
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
        offers[service.offer]["options"].append({
            "label": str(service),
            "value": service.id,
        })

    return JsonResponse({
        "id": project.id,
        "code": project.code,
        "title": project.title,
        "owned_by": project.owned_by.get_short_name(),
        "customer_id": project.customer_id,
        "services": [data for offer, data in sorted(offers.items()) if data["options"]],
    })


def projects(request):
    return JsonResponse({
        "projects": [
            {"label": str(project), "value": project.pk}
            for project in request.user.active_projects
        ],
    })


def cost_by_month_and_service_xlsx(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project_costs = defaultdict(lambda: Z2)
    service_costs = defaultdict(lambda: defaultdict(lambda: Z2))
    offer_costs = defaultdict(lambda: defaultdict(lambda: Z2))
    offers = defaultdict(set)
    months = set()

    for hours in LoggedHours.objects.filter(service__project=project).select_related(
        "service__offer"
    ):
        month = hours.rendered_on.replace(day=1)
        months.add(month)

        c = (hours.service.effort_rate or 0) * hours.hours
        project_costs[month] += c
        service_costs[hours.service][month] += c
        offer_costs[hours.service.offer][month] += c
        offers[hours.service.offer].add(hours.service)

    for cost in LoggedCost.objects.filter(service__project=project).select_related(
        "service__offer"
    ):
        month = cost.rendered_on.replace(day=1)
        months.add(month)

        project_costs[month] += cost.cost
        service_costs[cost.service][month] += cost.cost
        offer_costs[cost.service.offer][month] += cost.cost
        offers[cost.service.offer].add(cost.service)

    months = sorted(months)

    rows = []
    rows.extend((
        [_("Cost by month and service")],
        ["", _("cost"), "", _("cost")]
        + [local_date_format(month, fmt="F Y") for month in months],
        [_("project")],
        [project, sum(project_costs.values()), "", ""]
        + [project_costs.get(month) for month in months],
        [],
        [_("offer or service group"), "", _("service"), ""],
    ))

    for offer, services in sorted(offers.items()):
        rows.append(
            [
                offer,
                sum(offer_costs[offer].values()),
                "",
                "",
            ]
            + [offer_costs[offer].get(month) for month in months]
        )
        for service in sorted(services):
            rows.append(
                [
                    "",
                    "",
                    service,
                    sum(service_costs[service].values()),
                ]
                + [service_costs[service].get(month) for month in months]
            )
        rows.append([])

    xlsx = XLSXDocument()
    xlsx.add_sheet(_("Statistics"))
    xlsx.table(None, rows)
    return xlsx.to_response(f"project-{project.id}.xlsx")
