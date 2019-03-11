from decimal import Decimal

from django.db.models import Sum

from workbench.logbook.models import LoggedHours
from workbench.projects.models import Project, Service


Z = Decimal("0.0")


def overdrawn_projects():
    projects = (
        Project.objects.open()
        .filter(maintenance=False)
        .select_related("customer", "owned_by")
    )

    logged_hours = {
        row["service__project"]: row["hours__sum"]
        for row in LoggedHours.objects.order_by()
        .filter(service__project__in=projects)
        .values("service__project")
        .annotate(Sum("hours"))
    }

    service_hours = {
        row["project"]: row["service_hours__sum"]
        for row in Service.objects.order_by()
        .filter(project__in=projects)
        .values("project")
        .annotate(Sum("service_hours"))
    }

    projects = [
        {
            "project": project,
            "logged_hours": logged_hours.get(project.id, Z),
            "service_hours": service_hours.get(project.id, Z),
            "delta": logged_hours.get(project.id, Z) - service_hours.get(project.id, Z),
        }
        for project in projects
    ]

    return sorted(
        (
            project
            for project in projects
            if project["logged_hours"] > project["service_hours"]
        ),
        key=lambda row: row["delta"],
        reverse=True,
    )
