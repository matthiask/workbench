from django.conf.urls import url
from django.shortcuts import redirect

from workbench.invoices.forms import CreateInvoiceForm
from workbench.invoices.models import Invoice
from workbench.logbook.forms import LoggedHoursForm, LoggedCostForm
from workbench.logbook.models import LoggedHours, LoggedCost
from workbench.offers.forms import CreateOfferForm
from workbench.offers.models import Offer, Service
from workbench.projects.forms import ProjectSearchForm, ProjectForm, ApprovedHoursForm
from workbench.projects.models import Project
from workbench.projects.views import (
    ProjectDetailView,
    CreateRelatedView,
    ServiceListView,
)
from workbench.generic import ListView, CreateView, UpdateView, DeleteView


urlpatterns = [
    url(
        r"^$",
        ListView.as_view(model=Project, search_form_class=ProjectSearchForm),
        name="projects_project_list",
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
        r"^(?P<pk>\d+)/costs/$",
        ProjectDetailView.as_view(project_view="costs"),
        name="projects_project_costs",
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
        r"^(?P<pk>\d+)/approved-hours/$",
        UpdateView.as_view(form_class=ApprovedHoursForm, model=Project),
        name="projects_project_approved_hours",
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
    # url(
    #     r'^(?P<pk>\d+)/estimation/$',
    #     EstimationView.as_view(),
    #     name='projects_project_estimation'),
    # url(
    #     r'^(?P<pk>\d+)/planning/$',
    #     views.PlanningView.as_view(),
    #     name='projects_project_planning'),
    url(
        r"^(?P<pk>\d+)/services/$",
        ServiceListView.as_view(model=Service, show_create_button=False),
        name="projects_project_services",
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
    url(
        r"^cost/(?P<pk>\d+)/update/$",
        UpdateView.as_view(model=LoggedCost, form_class=LoggedCostForm),
        name="logbook_loggedcost_update",
    ),
    url(
        r"^cost/(?P<pk>\d+)/delete/$",
        DeleteView.as_view(model=LoggedCost, template_name="modal_confirm_delete.html"),
        name="logbook_loggedcost_delete",
    ),
]
