from django.shortcuts import get_object_or_404, render

from workbench import generic
from workbench.accounts.models import Team, User
from workbench.planning import reporting
from workbench.projects.models import Project


class ProjectPlanningView(generic.DetailView):
    model = Project
    template_name = "planning/project_planning.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            planning_data=reporting.project_planning(self.object), **kwargs
        )


def user_planning(request, pk):
    instance = get_object_or_404(User.objects.active(), pk=pk)
    return render(
        request,
        "planning/user_planning.html",
        {
            "object": instance,
            "user": instance,
            "planning_data": reporting.user_planning(instance),
        },
    )


def team_planning(request, pk):
    instance = get_object_or_404(Team.objects.all(), pk=pk)
    return render(
        request,
        "planning/team_planning.html",
        {
            "object": instance,
            "team": instance,
            "planning_data": reporting.team_planning(instance),
        },
    )
