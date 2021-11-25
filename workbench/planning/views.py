from django.shortcuts import get_object_or_404, render

from workbench.accounts.models import Team, User
from workbench.planning import reporting
from workbench.projects.models import Campaign, Project
from workbench.tools.validation import in_days


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


def project_planning_external(request, pk):
    instance = get_object_or_404(Project.objects.all(), pk=pk)
    return render(
        request,
        "planning/project_planning_external.html",
        {
            "object": instance,
            "project": instance,
            "planning_data": reporting.project_planning_external(instance),
        },
    )


def user_planning(request, pk, retro=False):
    instance = get_object_or_404(User.objects.active(), pk=pk)
    date_range = [in_days(-180), in_days(14)] if retro else [in_days(-14), in_days(400)]

    return render(
        request,
        "planning/user_planning.html",
        {
            "object": instance,
            "user": instance,
            "planning_data": reporting.user_planning(instance, date_range),
        },
    )


def team_planning(request, pk, retro=False):
    instance = get_object_or_404(Team.objects.all(), pk=pk)
    date_range = [in_days(-180), in_days(14)] if retro else [in_days(-14), in_days(400)]

    return render(
        request,
        "planning/team_planning.html",
        {
            "object": instance,
            "team": instance,
            "planning_data": reporting.team_planning(instance, date_range),
        },
    )


def campaign_planning(request, pk):
    instance = get_object_or_404(Campaign.objects.all(), pk=pk)
    return render(
        request,
        "planning/campaign_planning.html",
        {
            "object": instance,
            "campaign": instance,
            "planning_data": reporting.campaign_planning(instance),
        },
    )


def campaign_planning_external(request, pk):
    instance = get_object_or_404(Campaign.objects.all(), pk=pk)
    return render(
        request,
        "planning/campaign_planning_external.html",
        {
            "object": instance,
            "campaign": instance,
            "planning_data": reporting.campaign_planning_external(instance),
        },
    )
