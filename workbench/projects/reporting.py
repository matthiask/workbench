from collections import defaultdict

from django.db.models import Sum

from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.logbook.models import LoggedHours
from workbench.projects.models import Project, Service
from workbench.tools.models import Z


def overdrawn_projects():
    projects = (
        Project.objects.open()
        .exclude(type=Project.INTERNAL)
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

    TYPE_ORDERING = {Project.ORDER: 1, Project.ACQUISITION: 1, Project.MAINTENANCE: 2}

    return sorted(
        (
            project
            for project in projects
            if project["logged_hours"] > project["service_hours"]
        ),
        key=lambda row: (TYPE_ORDERING.get(row["project"].type, 9), -row["delta"]),
    )


def hours_per_customer(date_range):
    hours = defaultdict(lambda: defaultdict(lambda: Z))
    seen_organizations = set()
    users = {user.id: user for user in User.objects.all()}

    for row in (
        LoggedHours.objects.order_by()
        .filter(rendered_on__range=date_range)
        .values("rendered_by", "service__project__customer")
        .annotate(Sum("hours"))
    ):
        hours[users[row["rendered_by"]]][row["service__project__customer"]] = row[
            "hours__sum"
        ]
        seen_organizations.add(row["service__project__customer"])

    organizations = {
        org.id: org for org in Organization.objects.filter(id__in=seen_organizations)
    }
    users = []
    for user, user_hours in sorted(hours.items()):
        user_data = [
            (organizations[org_id], hours)
            for org_id, hours in sorted(
                user_hours.items(), key=lambda row: row[1], reverse=True
            )
        ]
        users.append(
            (user, user_data[:6] + [("Rest", sum(row[1] for row in user_data[6:]))])
        )
    return users
