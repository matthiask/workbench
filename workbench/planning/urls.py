from django.urls import path

from workbench import generic
from workbench.logbook.views import create
from workbench.planning.forms import (
    ExternalWorkForm,
    ExternalWorkSearchForm,
    MilestoneForm,
    MilestoneSearchForm,
    PlannedWorkForm,
    PlannedWorkSearchForm,
)
from workbench.planning.models import (
    ExternalWork,
    Milestone,
    PlannedWork,
    PublicHoliday,
)
from workbench.projects.models import Project


urlpatterns = [
    # Milestones
    path(
        "milestone/",
        generic.ListView.as_view(
            model=Milestone,
            search_form_class=MilestoneSearchForm,
            show_create_button=False,
        ),
        name="planning_milestone_list",
    ),
    path(
        "milestone/<int:pk>/",
        generic.DetailView.as_view(model=Milestone),
        name="planning_milestone_detail",
    ),
    path(
        "milestone/create/",
        create,
        {"viewname": "createmilestone"},
        name="planning_milestone_create",
    ),
    path(
        "milestone/create/<int:pk>/",
        generic.CreateRelatedView.as_view(
            model=Milestone, form_class=MilestoneForm, related_model=Project
        ),
        name="projects_project_createmilestone",
    ),
    path(
        "milestone/<int:pk>/update/",
        generic.UpdateView.as_view(model=Milestone, form_class=MilestoneForm),
        name="planning_milestone_update",
    ),
    path(
        "milestone/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=Milestone, template_name="modal_confirm_delete.html"
        ),
        name="planning_milestone_delete",
    ),
    # Work
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
    # External
    path(
        "externalwork/",
        generic.ListView.as_view(
            model=ExternalWork, search_form_class=ExternalWorkSearchForm
        ),
        name="planning_externalwork_list",
    ),
    path(
        "externalwork/<int:pk>/",
        generic.DetailView.as_view(model=ExternalWork),
        name="planning_externalwork_detail",
    ),
    path(
        "externalwork/create/",
        create,
        {"viewname": "createexternalwork"},
        name="planning_externalwork_create",
    ),
    path(
        "externalwork/create/<int:pk>/",
        generic.CreateRelatedView.as_view(
            model=ExternalWork, form_class=ExternalWorkForm, related_model=Project
        ),
        name="projects_project_createexternalwork",
    ),
    path(
        "externalwork/<int:pk>/update/",
        generic.UpdateView.as_view(model=ExternalWork, form_class=ExternalWorkForm),
        name="planning_externalwork_update",
    ),
    path(
        "externalwork/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=ExternalWork, template_name="modal_confirm_delete.html"
        ),
        name="planning_externalwork_delete",
    ),
    # Public holidays
    path(
        "ph/<int:pk>/",
        generic.DetailView.as_view(model=PublicHoliday),
        name="planning_publicholiday_detail",
    ),
]
