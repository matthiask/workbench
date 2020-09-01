from django.urls import path

from workbench import generic
from workbench.logbook.views import create
from workbench.planning.forms import (
    PlannedWorkForm,
    PlannedWorkSearchForm,
    PlanningRequestForm,
    PlanningRequestSearchForm,
)
from workbench.planning.models import PlannedWork, PlanningRequest
from workbench.projects.models import Project


urlpatterns = [
    # Requests
    path(
        "requests/",
        generic.ListView.as_view(
            model=PlanningRequest, search_form_class=PlanningRequestSearchForm
        ),
        name="planning_planningrequest_list",
    ),
    path(
        "requests/<int:pk>/",
        generic.DetailView.as_view(model=PlanningRequest),
        name="planning_planningrequest_detail",
    ),
    path(
        "requests/create/",
        create,
        {"viewname": "createrequest"},
        name="planning_planningrequest_create",
    ),
    path(
        "requests/create/<int:pk>/",
        generic.CreateRelatedView.as_view(
            model=PlanningRequest, form_class=PlanningRequestForm, related_model=Project
        ),
        name="projects_project_createrequest",
    ),
    path(
        "requests/<int:pk>/update/",
        generic.UpdateView.as_view(
            model=PlanningRequest,
            form_class=PlanningRequestForm,
        ),
        name="planning_planningrequest_update",
    ),
    path(
        "requests/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=PlanningRequest, template_name="modal_confirm_delete.html"
        ),
        name="planning_planningrequest_delete",
    ),
    # Planned work
    path(
        "work/",
        generic.ListView.as_view(
            model=PlannedWork, search_form_class=PlannedWorkSearchForm
        ),
        name="planning_plannedwork_list",
    ),
    path(
        "work/<int:pk>/",
        generic.DetailView.as_view(model=PlannedWork),
        name="planning_plannedwork_detail",
    ),
    path(
        "work/create/",
        create,
        {"viewname": "creatework"},
        name="planning_plannedwork_create",
    ),
    path(
        "work/create/<int:pk>/",
        generic.CreateRelatedView.as_view(
            model=PlannedWork, form_class=PlannedWorkForm, related_model=Project
        ),
        name="projects_project_creatework",
    ),
    path(
        "work/<int:pk>/update/",
        generic.UpdateView.as_view(model=PlannedWork, form_class=PlannedWorkForm),
        name="planning_plannedwork_update",
    ),
    path(
        "work/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=PlannedWork, template_name="modal_confirm_delete.html"
        ),
        name="planning_plannedwork_delete",
    ),
]
