import datetime as dt
from collections import defaultdict

from django.db.models import Sum

from workbench.accruals.models import Accrual
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.tools.models import Z


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

    accruals_per_project = defaultdict(lambda: Z)
    for accrual in Accrual.objects.generate_accruals(
        cutoff_date=dt.date.today(), save=False
    )["accruals"]:
        accruals_per_project[accrual.invoice.project_id] -= accrual.accrual

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
            "delta": cost_per_project.get(project.id, Z)
            + effort_cost_per_project[project.id]
            - invoiced_per_project.get(project.id, Z),
            "accrual": accruals_per_project[project.id],
        }
        for project in projects
    ]
