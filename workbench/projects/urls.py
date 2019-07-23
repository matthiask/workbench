from django.conf.urls import url
from django.shortcuts import get_object_or_404, redirect

from workbench import generic
from workbench.invoices.forms import CreateProjectInvoiceForm
from workbench.invoices.models import Invoice
from workbench.logbook.forms import LoggedCostForm, LoggedHoursForm
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.forms import OfferForm
from workbench.offers.models import Offer
from workbench.offers.views import ProjectOfferPDFView
from workbench.projects.forms import (
    ProjectForm,
    ProjectSearchForm,
    ServiceDeleteForm,
    ServiceForm,
    ServiceMoveForm,
)
from workbench.projects.models import Project, Service
from workbench.projects.views import select, set_order


def autocomplete_filter(*, request, queryset):
    return (
        queryset.filter(closed_on__isnull=True)
        if request.GET.get("only_open")
        else queryset
    )


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=Project, search_form_class=ProjectSearchForm),
        name="projects_project_list",
    ),
    url(
        r"^autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Project,
            queryset=Project.objects.select_related("owned_by"),
            filter=autocomplete_filter,
        ),
        name="projects_project_autocomplete",
    ),
    url(r"^select/$", select, name="projects_project_select"),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(
            model=Project,
            queryset=Project.objects.select_related(
                "owned_by", "customer", "contact__organization"
            ),
        ),
        name="projects_project_detail",
    ),
    url(
        r"^(?P<pk>\d+)/statistics/$",
        generic.DetailView.as_view(model=Project, template_name_suffix="_statistics"),
        name="projects_project_statistics",
    ),
    url(
        r"^(?P<pk>\d+)/offers-pdf/$",
        ProjectOfferPDFView.as_view(),
        name="projects_project_offers_pdf",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Project),
        name="projects_project_delete",
    ),
    url(
        r"^(?P<pk>\d+)/createoffer/$",
        generic.CreateRelatedView.as_view(
            model=Offer, form_class=OfferForm, related_model=Project
        ),
        name="projects_project_createoffer",
    ),
    url(
        r"^(?P<pk>\d+)/createinvoice/$",
        generic.CreateRelatedView.as_view(
            model=Invoice, form_class=CreateProjectInvoiceForm, related_model=Project
        ),
        name="projects_project_createinvoice",
    ),
    # HOURS
    url(
        r"^(?P<pk>\d+)/createhours/$",
        generic.CreateRelatedView.as_view(
            model=LoggedHours, form_class=LoggedHoursForm, related_model=Project
        ),
        name="projects_project_createhours",
    ),
    # COSTS
    url(
        r"^(?P<pk>\d+)/createcost/$",
        generic.CreateRelatedView.as_view(
            model=LoggedCost, form_class=LoggedCostForm, related_model=Project
        ),
        name="projects_project_createcost",
    ),
    # Services
    url(
        r"^(?P<pk>\d+)/createservice/$",
        generic.CreateRelatedView.as_view(
            model=Service, form_class=ServiceForm, related_model=Project
        ),
        name="projects_project_createservice",
    ),
    url(
        r"^service/(?P<pk>\d+)/$",
        lambda request, pk: redirect(get_object_or_404(Service, pk=pk)),
        name="projects_service_detail",
    ),
    url(
        r"^service/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=Service, form_class=ServiceForm),
        name="projects_service_update",
    ),
    url(
        r"^service/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Service,
            delete_form_class=ServiceDeleteForm,
            template_name_suffix="_merge",
        ),
        name="projects_service_delete",
    ),
    url(
        r"^service/(?P<pk>\d+)/move/$",
        generic.UpdateView.as_view(
            model=Service, form_class=ServiceMoveForm, template_name="modalform.html"
        ),
        name="projects_service_move",
    ),
    url(r"^service/set-order/$", set_order, name="projects_service_set_order"),
]
