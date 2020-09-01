from django.shortcuts import get_object_or_404, redirect
from django.urls import include, re_path
from django.utils.translation import gettext_lazy as _

from workbench import generic
from workbench.accounts.features import controlling_only
from workbench.invoices.forms import CreateProjectInvoiceForm
from workbench.invoices.models import Invoice
from workbench.logbook.forms import LoggedCostForm, LoggedHoursForm
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.forms import OfferForm
from workbench.offers.models import Offer
from workbench.offers.views import ProjectOfferPDFView
from workbench.planning.views import ProjectPlanningView
from workbench.projects.forms import (
    CampaignDeleteForm,
    CampaignForm,
    CampaignSearchForm,
    ProjectForm,
    ProjectSearchForm,
    ReassignLogbookForm,
    ServiceForm,
    ServiceMoveForm,
)
from workbench.projects.models import Campaign, Project, Service
from workbench.projects.views import (
    OffersRenumberView,
    assign_service_type,
    projects,
    select,
    services,
    set_order,
)


def autocomplete_filter(*, request, queryset):
    return (
        queryset.filter(closed_on__isnull=True)
        if request.GET.get("only_open")
        else queryset
    )


urlpatterns = [
    re_path(r"^offers/", include("workbench.offers.urls")),
    # Campaigns
    re_path(
        r"^campaigns/$",
        generic.ListView.as_view(model=Campaign, search_form_class=CampaignSearchForm),
        name="projects_campaign_list",
    ),
    re_path(
        r"^campaigns/autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Campaign,
            queryset=Campaign.objects.select_related("owned_by"),
            filter=autocomplete_filter,
        ),
        name="projects_campaign_autocomplete",
    ),
    re_path(
        r"^campaigns/(?P<pk>\d+)/$",
        generic.DetailView.as_view(
            model=Campaign,
            queryset=Campaign.objects.select_related("owned_by", "customer"),
        ),
        name="projects_campaign_detail",
    ),
    re_path(
        r"^campaigns/create/$",
        generic.CreateView.as_view(form_class=CampaignForm, model=Campaign),
        name="projects_campaign_create",
    ),
    re_path(
        r"^campaigns/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=CampaignForm, model=Campaign),
        name="projects_campaign_update",
    ),
    re_path(
        r"^campaigns/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Campaign, delete_form_class=CampaignDeleteForm
        ),
        name="projects_campaign_delete",
    ),
    # Projects
    re_path(
        r"^$",
        generic.ListView.as_view(model=Project, search_form_class=ProjectSearchForm),
        name="projects_project_list",
    ),
    re_path(
        r"^autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Project,
            queryset=Project.objects.select_related("owned_by"),
            filter=autocomplete_filter,
        ),
        name="projects_project_autocomplete",
    ),
    re_path(r"^select/$", select, name="projects_project_select"),
    re_path(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(
            model=Project,
            queryset=Project.objects.select_related(
                "owned_by", "customer", "contact__organization"
            ),
        ),
        name="projects_project_detail",
    ),
    re_path(
        r"^(?P<pk>\d+)/statistics/$",
        generic.DetailView.as_view(model=Project, template_name_suffix="_statistics"),
        name="projects_project_statistics",
    ),
    re_path(
        r"^(?P<pk>\d+)/planning/$",
        ProjectPlanningView.as_view(),
        name="projects_project_planning",
    ),
    re_path(
        r"^(?P<pk>\d+)/offers-pdf/$",
        controlling_only(ProjectOfferPDFView.as_view()),
        name="projects_project_offers_pdf",
    ),
    re_path(
        r"^(?P<pk>\d+)/renumber-offers/$",
        controlling_only(
            OffersRenumberView.as_view(
                model=Project, template_name_suffix="_renumber_offers"
            )
        ),
        name="projects_project_renumber_offers",
    ),
    re_path(
        r"^create/$",
        generic.CreateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_create",
    ),
    re_path(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_update",
    ),
    re_path(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Project),
        name="projects_project_delete",
    ),
    re_path(
        r"^(?P<pk>\d+)/createoffer/$",
        generic.CreateRelatedView.as_view(
            model=Offer, form_class=OfferForm, related_model=Project
        ),
        name="projects_project_createoffer",
    ),
    re_path(
        r"^(?P<pk>\d+)/createinvoice/$",
        generic.CreateRelatedView.as_view(
            model=Invoice, form_class=CreateProjectInvoiceForm, related_model=Project
        ),
        name="projects_project_createinvoice",
    ),
    # HOURS
    re_path(
        r"^(?P<pk>\d+)/createhours/$",
        generic.CreateRelatedView.as_view(
            model=LoggedHours, form_class=LoggedHoursForm, related_model=Project
        ),
        name="projects_project_createhours",
    ),
    # COSTS
    re_path(
        r"^(?P<pk>\d+)/createcost/$",
        generic.CreateRelatedView.as_view(
            model=LoggedCost, form_class=LoggedCostForm, related_model=Project
        ),
        name="projects_project_createcost",
    ),
    # Services
    re_path(
        r"^(?P<pk>\d+)/createservice/$",
        generic.CreateRelatedView.as_view(
            model=Service, form_class=ServiceForm, related_model=Project
        ),
        name="projects_project_createservice",
    ),
    re_path(
        r"^service/(?P<pk>\d+)/$",
        lambda request, pk: redirect(get_object_or_404(Service, pk=pk)),
        name="projects_service_detail",
    ),
    re_path(
        r"^service/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=Service, form_class=ServiceForm),
        name="projects_service_update",
    ),
    re_path(
        r"^service/(?P<pk>\d+)/reassign-logbook/$",
        generic.UpdateView.as_view(
            model=Service,
            form_class=ReassignLogbookForm,
            template_name="modalform.html",
            title=_("Reassign logbook entries of %(instance)s"),
        ),
        name="projects_service_reassign_logbook",
    ),
    re_path(
        r"^service/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Service, template_name="modal_confirm_delete.html"
        ),
        name="projects_service_delete",
    ),
    re_path(
        r"^service/(?P<pk>\d+)/move/$",
        generic.UpdateView.as_view(
            model=Service, form_class=ServiceMoveForm, template_name="modalform.html"
        ),
        name="projects_service_move",
    ),
    re_path(
        r"^service/(?P<pk>\d+)/assign-service-type/$",
        assign_service_type,
        name="projects_service_assign_service_type",
    ),
    re_path(r"^service/set-order/$", set_order, name="projects_service_set_order"),
    re_path(
        r"^(?P<pk>[0-9]+)/services/$",
        services,
        name="projects_project_services",
    ),
    re_path(r"^projects/$", projects, name="projects_project_projects"),
    re_path(
        r"^service/autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Service,
            queryset=Service.objects.filter(
                project__closed_on__isnull=True
            ).select_related("project__owned_by"),
            label_from_instance=lambda service: "{} ({})".format(
                service, service.project
            ),
        ),
        name="projects_service_autocomplete",
    ),
]
