from django.conf.urls import url
from django.shortcuts import get_object_or_404, redirect

from workbench.invoices.forms import CreateInvoiceForm
from workbench.invoices.models import Invoice
from workbench.logbook.forms import LoggedHoursForm, LoggedCostForm
from workbench.logbook.models import LoggedHours, LoggedCost
from workbench.offers.forms import CreateOfferForm
from workbench.offers.models import Offer
from workbench.projects.forms import (
    ProjectSearchForm,
    ProjectForm,
    ServiceForm,
    DeleteServiceForm,
)
from workbench.projects.models import Project, Service
from workbench.projects.views import (
    ProjectDetailView,
    CreateRelatedView,
    UpdateServiceView,
    MoveServiceView,
)
from workbench.generic import ListView, CreateView, UpdateView, DeleteView


urlpatterns = [
    url(
        r"^$",
        ListView.as_view(model=Project, search_form_class=ProjectSearchForm),
        name="projects_project_list",
    ),
    url(
        r"^picker/$",
        ListView.as_view(model=Project, template_name_suffix="_picker", paginate_by=10),
        name="projects_project_picker",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        lambda request, pk: redirect("overview/"),
        name="projects_project_detail",
    ),
    url(
        r"^(?P<pk>\d+)/overview/$",
        ProjectDetailView.as_view(project_view="overview"),
        name="projects_project_overview",
    ),
    url(
        r"^(?P<pk>\d+)/services/$",
        ProjectDetailView.as_view(project_view="services"),
        name="projects_project_services",
    ),
    url(
        r"^(?P<pk>\d+)/activities/$",
        ProjectDetailView.as_view(project_view="activities"),
        name="projects_project_activities",
    ),
    url(
        r"^create/$",
        CreateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        UpdateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        DeleteView.as_view(model=Project),
        name="projects_project_delete",
    ),
    url(
        r"^(?P<pk>\d+)/createoffer/$",
        CreateRelatedView.as_view(model=Offer, form_class=CreateOfferForm),
        name="projects_project_createoffer",
    ),
    url(
        r"^(?P<pk>\d+)/createinvoice/$",
        CreateRelatedView.as_view(model=Invoice, form_class=CreateInvoiceForm),
        name="projects_project_createinvoice",
    ),
    # HOURS
    url(
        r"^(?P<pk>\d+)/createhours/$",
        CreateRelatedView.as_view(model=LoggedHours, form_class=LoggedHoursForm),
        name="projects_project_createhours",
    ),
    # COSTS
    url(
        r"^(?P<pk>\d+)/createcost/$",
        CreateRelatedView.as_view(model=LoggedCost, form_class=LoggedCostForm),
        name="projects_project_createcost",
    ),
    # Services
    url(
        r"^(?P<pk>\d+)/createservice/$",
        CreateRelatedView.as_view(model=Service, form_class=ServiceForm),
        name="projects_project_createservice",
    ),
    url(
        r"^service/(?P<pk>\d+)/$",
        lambda request, pk: redirect(
            get_object_or_404(Service, pk=pk).project.urls.url("services")
        ),
        name="projects_service_detail",
    ),
    url(
        r"^service/(?P<pk>\d+)/update/$",
        UpdateServiceView.as_view(),
        name="projects_service_update",
    ),
    url(
        r"^service/(?P<pk>\d+)/delete/$",
        UpdateServiceView.as_view(
            form_class=DeleteServiceForm, template_name_suffix="_merge"
        ),
        name="projects_service_delete",
    ),
    url(
        r"^service/(?P<pk>\d+)/move/$",
        MoveServiceView.as_view(),
        name="projects_service_move",
    ),
]
