from django.conf.urls import url
from django.shortcuts import get_object_or_404, redirect

from workbench import generic
from workbench.invoices.forms import CreateProjectInvoiceForm
from workbench.invoices.models import Invoice
from workbench.logbook.forms import LoggedHoursForm, LoggedCostForm
from workbench.logbook.models import LoggedHours, LoggedCost
from workbench.offers.forms import OfferForm
from workbench.offers.models import Offer
from workbench.projects.forms import (
    ProjectSearchForm,
    ProjectForm,
    ServiceForm,
    DeleteServiceForm,
)
from workbench.projects.models import Project, Service
from workbench.projects.views import CreateRelatedView, MoveServiceView


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=Project, search_form_class=ProjectSearchForm),
        name="projects_project_list",
    ),
    url(
        r"^picker/$",
        generic.ListView.as_view(
            model=Project, template_name_suffix="_picker", paginate_by=10
        ),
        name="projects_project_picker",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        lambda request, pk: redirect("overview/"),
        name="projects_project_detail",
    ),
    url(
        r"^(?P<pk>\d+)/overview/$",
        generic.DetailView.as_view(
            model=Project, template_name_suffix="_detail_overview"
        ),
        name="projects_project_overview",
    ),
    url(
        r"^(?P<pk>\d+)/services/$",
        generic.DetailView.as_view(
            model=Project, template_name_suffix="_detail_services"
        ),
        name="projects_project_services",
    ),
    url(
        r"^(?P<pk>\d+)/activities/$",
        generic.DetailView.as_view(
            model=Project, template_name_suffix="_detail_activities"
        ),
        name="projects_project_activities",
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
        CreateRelatedView.as_view(model=Offer, form_class=OfferForm),
        name="projects_project_createoffer",
    ),
    url(
        r"^(?P<pk>\d+)/createinvoice/$",
        CreateRelatedView.as_view(model=Invoice, form_class=CreateProjectInvoiceForm),
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
        generic.UpdateView.as_view(model=Service, form_class=ServiceForm),
        name="projects_service_update",
    ),
    url(
        r"^service/(?P<pk>\d+)/delete/$",
        generic.UpdateView.as_view(
            model=Service, form_class=DeleteServiceForm, template_name_suffix="_merge"
        ),
        name="projects_service_delete",
    ),
    url(
        r"^service/(?P<pk>\d+)/move/$",
        MoveServiceView.as_view(),
        name="projects_service_move",
    ),
]
