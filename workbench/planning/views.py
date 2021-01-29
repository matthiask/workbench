from django.shortcuts import get_object_or_404, render

from workbench.accounts.models import Team, User
from workbench.planning import reporting
from workbench.projects.models import Project


def project_planning(request, pk):
    instance = get_object_or_404(Project.objects.all(), pk=pk)
    return render(
        request,
        "planning/project_planning.html",
        {
            "object": instance,
            "project": instance,
            "planning_data": reporting.project_planning(instance),
        },
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
