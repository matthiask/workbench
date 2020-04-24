from collections import defaultdict

from django.db.models import Sum

from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.logbook.models import LoggedHours
from workbench.projects.models import Project, Service
from workbench.tools.formats import Z1


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
            "logged_hours": logged_hours.get(project.id, Z1),
            "service_hours": service_hours.get(project.id, Z1),
            "delta": logged_hours.get(project.id, Z1)
            - service_hours.get(project.id, Z1),
        }
        for project in projects
    ]

    TYPE_ORDERING = {Project.ORDER: 1, Project.MAINTENANCE: 2}

    return sorted(
        (
            project
            for project in projects
            if project["logged_hours"] > project["service_hours"]
        ),
        key=lambda row: (TYPE_ORDERING.get(row["project"].type, 9), -row["delta"]),
    )


def hours_per_customer(date_range, *, users=None):
    hours = defaultdict(lambda: defaultdict(lambda: Z1))
    user_hours = defaultdict(lambda: Z1)
    seen_organizations = set()
    seen_users = set()

    queryset = LoggedHours.objects.order_by().filter(rendered_on__range=date_range)
    if users:
        queryset = queryset.filter(rendered_by__in=users)

    for row in queryset.values("rendered_by", "service__project__customer").annotate(
        Sum("hours")
    ):
        hours[row["service__project__customer"]][row["rendered_by"]] = row["hours__sum"]
        user_hours[row["rendered_by"]] += row["hours__sum"]
        seen_organizations.add(row["service__project__customer"])
        seen_users.add(row["rendered_by"])

    organizations = []
    user_list = User.objects.filter(id__in=seen_users)

    for org in Organization.objects.filter(id__in=seen_organizations):
        organizations.append(
            {
                "organization": org,
                "user_hours": [(user, hours[org.id][user.id]) for user in user_list],
                "total_hours": sum(hours[org.id].values(), Z1),
            }
        )

    return {
        "organizations": sorted(
            organizations, key=lambda row: row["total_hours"], reverse=True
        ),
        "users": user_list,
        "user_hours": [(user, user_hours[user.id]) for user in user_list],
        "total_hours": sum(user_hours.values(), Z1),
    }
