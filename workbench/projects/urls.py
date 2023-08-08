from django.shortcuts import get_object_or_404, redirect
from django.urls import include, path
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
from workbench.planning.views import (
    campaign_planning,
    campaign_planning_external,
    project_planning,
    project_planning_external,
)
from workbench.projects.forms import (
    CampaignDeleteForm,
    CampaignForm,
    CampaignSearchForm,
    ProjectedInvoicesProjectForm,
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
    cost_by_month_and_service_xlsx,
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
    path("offers/", include("workbench.offers.urls")),
    # Campaigns
    path(
        "campaigns/",
        generic.ListView.as_view(model=Campaign, search_form_class=CampaignSearchForm),
        name="projects_campaign_list",
    ),
    path(
        "campaigns/autocomplete/",
        generic.AutocompleteView.as_view(
            model=Campaign,
            queryset=Campaign.objects.select_related("owned_by"),
            filter=autocomplete_filter,
        ),
        name="projects_campaign_autocomplete",
    ),
    path(
        "campaigns/<int:pk>/",
        generic.DetailView.as_view(
            model=Campaign,
            queryset=Campaign.objects.select_related("owned_by", "customer"),
        ),
        name="projects_campaign_detail",
    ),
    path(
        "campaigns/<int:pk>/statistics/",
        generic.DetailView.as_view(model=Campaign, template_name_suffix="_statistics"),
        name="projects_campaign_statistics",
    ),
    path(
        "campaigns/create/",
        generic.CreateView.as_view(form_class=CampaignForm, model=Campaign),
        name="projects_campaign_create",
    ),
    path(
        "campaigns/<int:pk>/update/",
        generic.UpdateView.as_view(form_class=CampaignForm, model=Campaign),
        name="projects_campaign_update",
    ),
    path(
        "campaigns/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=Campaign, delete_form_class=CampaignDeleteForm
        ),
        name="projects_campaign_delete",
    ),
    path(
        "campaigns/<int:pk>/planning/",
        campaign_planning,
        name="projects_campaign_planning",
    ),
    path(
        "campaigns/<int:pk>/external/",
        campaign_planning_external,
        name="projects_campaign_planning_external",
    ),
    # Projects
    path(
        "",
        generic.ListView.as_view(model=Project, search_form_class=ProjectSearchForm),
        name="projects_project_list",
    ),
    path(
        "autocomplete/",
        generic.AutocompleteView.as_view(
            model=Project,
            queryset=Project.objects.select_related("owned_by"),
            filter=autocomplete_filter,
        ),
        name="projects_project_autocomplete",
    ),
    path("select/", select, name="projects_project_select"),
    path(
        "<int:pk>/",
        generic.DetailView.as_view(
            model=Project,
            queryset=Project.objects.select_related(
                "owned_by", "customer", "contact__organization"
            ),
        ),
        name="projects_project_detail",
    ),
    path(
        "<int:pk>/statistics/",
        generic.DetailView.as_view(model=Project, template_name_suffix="_statistics"),
        name="projects_project_statistics",
    ),
    path(
        "<int:pk>/cost-by-month-and-service-xlsx/",
        cost_by_month_and_service_xlsx,
        name="projects_project_cost_by_month_and_service_xlsx",
    ),
    path(
        "<int:pk>/planning/",
        project_planning,
        name="projects_project_planning",
    ),
    path(
        "<int:pk>/external/",
        project_planning_external,
        name="projects_project_planning_external",
    ),
    path(
        "<int:pk>/offers-pdf/",
        controlling_only(ProjectOfferPDFView.as_view()),
        name="projects_project_offers_pdf",
    ),
    path(
        "<int:pk>/renumber-offers/",
        controlling_only(
            OffersRenumberView.as_view(
                model=Project, template_name_suffix="_renumber_offers"
            )
        ),
        name="projects_project_renumber_offers",
    ),
    path(
        "create/",
        generic.CreateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_create",
    ),
    path(
        "<int:pk>/update/",
        generic.UpdateView.as_view(form_class=ProjectForm, model=Project),
        name="projects_project_update",
    ),
    path(
        "<int:pk>/projected-gross-margin/",
        generic.UpdateView.as_view(
            form_class=ProjectedInvoicesProjectForm,
            model=Project,
            template_name_suffix="_projected_invoices_form",
        ),
        name="projects_project_projected_invoices",
    ),
    path(
        "<int:pk>/delete/",
        generic.DeleteView.as_view(model=Project),
        name="projects_project_delete",
    ),
    path(
        "<int:pk>/createoffer/",
        generic.CreateRelatedView.as_view(
            model=Offer, form_class=OfferForm, related_model=Project
        ),
        name="projects_project_createoffer",
    ),
    path(
        "<int:pk>/createinvoice/",
        generic.CreateRelatedView.as_view(
            model=Invoice, form_class=CreateProjectInvoiceForm, related_model=Project
        ),
        name="projects_project_createinvoice",
    ),
    # HOURS
    path(
        "<int:pk>/createhours/",
        generic.CreateRelatedView.as_view(
            model=LoggedHours, form_class=LoggedHoursForm, related_model=Project
        ),
        name="projects_project_createhours",
    ),
    # COSTS
    path(
        "<int:pk>/createcost/",
        generic.CreateRelatedView.as_view(
            model=LoggedCost, form_class=LoggedCostForm, related_model=Project
        ),
        name="projects_project_createcost",
    ),
    # Services
    path(
        "<int:pk>/createservice/",
        generic.CreateRelatedView.as_view(
            model=Service, form_class=ServiceForm, related_model=Project
        ),
        name="projects_project_createservice",
    ),
    path(
        "service/<int:pk>/",
        lambda request, pk: redirect(get_object_or_404(Service, pk=pk)),
        name="projects_service_detail",
    ),
    path(
        "service/<int:pk>/update/",
        generic.UpdateView.as_view(model=Service, form_class=ServiceForm),
        name="projects_service_update",
    ),
    path(
        "service/<int:pk>/reassign-logbook/",
        generic.UpdateView.as_view(
            model=Service,
            form_class=ReassignLogbookForm,
            template_name="modalform.html",
            title=_("Reassign logbook entries of %(instance)s"),
        ),
        name="projects_service_reassign_logbook",
    ),
    path(
        "service/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=Service, template_name="modal_confirm_delete.html"
        ),
        name="projects_service_delete",
    ),
    path(
        "service/<int:pk>/move/",
        generic.UpdateView.as_view(
            model=Service, form_class=ServiceMoveForm, template_name="modalform.html"
        ),
        name="projects_service_move",
    ),
    path(
        "service/<int:pk>/assign-service-type/",
        assign_service_type,
        name="projects_service_assign_service_type",
    ),
    path("service/set-order/", set_order, name="projects_service_set_order"),
    path(
        "<int:pk>/services/",
        services,
        name="projects_project_services",
    ),
    path("projects/", projects, name="projects_project_projects"),
    path(
        "service/autocomplete/",
        generic.AutocompleteView.as_view(
            model=Service,
            queryset=Service.objects.filter(
                project__closed_on__isnull=True
            ).select_related("project__owned_by"),
            label_from_instance=lambda service: f"{service} ({service.project})",
        ),
        name="projects_service_autocomplete",
    ),
]
