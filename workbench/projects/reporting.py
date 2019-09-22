from collections import defaultdict

from django.db.models import Sum

from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
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
    hours = defaultdict(lambda: defaultdict(lambda: Z))
    user_hours = defaultdict(lambda: Z)
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
                "total_hours": sum(hours[org.id].values(), Z),
            }
        )

    return {
        "organizations": sorted(
            organizations, key=lambda row: row["total_hours"], reverse=True
        ),
        "users": user_list,
        "user_hours": [(user, user_hours[user.id]) for user in user_list],
        "total_hours": sum(user_hours.values(), Z),
    }


def project_budget_statistics(projects):
    costs = (
        LoggedCost.objects.filter(service__project__in=projects)
        .order_by()
        .values("service__project")
    )

    cost_per_project = {
        row["service__project"]: row["cost__sum"] for row in costs.annotate(Sum("cost"))
    }
    third_party_costs_per_project = {
        row["service__project"]: row["third_party_costs__sum"]
        for row in costs.filter(
            third_party_costs__isnull=False, invoice_service__isnull=True
        ).annotate(Sum("third_party_costs"))
    }

    hours = (
        LoggedHours.objects.filter(service__project__in=projects)
        .order_by()
        .values("service__project", "service__effort_rate")
        .annotate(Sum("hours"))
    )
    effort_cost_per_project = defaultdict(lambda: Z)
    effort_hours_with_rate_undefined_per_project = defaultdict(lambda: Z)
    hours_per_project = defaultdict(lambda: Z)

    for row in hours:
        if row["service__effort_rate"] is None:
            effort_hours_with_rate_undefined_per_project[
                row["service__project"]
            ] += row["hours__sum"]
        else:
            effort_cost_per_project[row["service__project"]] += (
                row["service__effort_rate"] * row["hours__sum"]
            )
        hours_per_project[row["service__project"]] += row["hours__sum"]

    not_archived_hours = {
        row["service__project"]: row["hours__sum"]
        for row in hours.filter(archived_at__isnull=True)
        .values("service__project")
        .annotate(Sum("hours"))
    }

    offered_per_project = {
        row["project"]: row["total_excl_tax__sum"]
        for row in Offer.objects.accepted()
        .filter(project__in=projects)
        .order_by()
        .values("project")
        .annotate(Sum("total_excl_tax"))
    }
    invoiced_per_project = {
        row["project"]: row["total_excl_tax__sum"]
        for row in Invoice.objects.valid()
        .filter(project__in=projects)
        .order_by()
        .values("project")
        .annotate(Sum("total_excl_tax"))
    }

    return [
        {
            "project": project,
            "logbook": cost_per_project.get(project.id, Z)
            + effort_cost_per_project[project.id],
            "cost": cost_per_project.get(project.id, Z),
            "effort_cost": effort_cost_per_project[project.id],
            "effort_hours_with_rate_undefined": effort_hours_with_rate_undefined_per_project[  # noqa
                project.id
            ],
            "third_party_costs": third_party_costs_per_project.get(project.id, Z),
            "offered": offered_per_project.get(project.id, Z),
            "invoiced": invoiced_per_project.get(project.id, Z),
            "hours": hours_per_project[project.id],
            "not_archived": not_archived_hours.get(project.id, Z),
        }
        for project in projects
    ]
