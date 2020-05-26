import datetime as dt
from collections import defaultdict

from django.db.models import Sum
from django.utils import timezone

from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.tools.formats import Z1, Z2


def project_budget_statistics(projects, *, cutoff_date=None):
    cutoff_date = cutoff_date or dt.date.today()
    cutoff_dttm = timezone.make_aware(dt.datetime.combine(cutoff_date, dt.time.max))

    costs = (
        LoggedCost.objects.filter(
            service__project__in=projects, rendered_on__lte=cutoff_dttm
        )
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
        LoggedHours.objects.filter(
            service__project__in=projects, rendered_on__lte=cutoff_dttm
        )
        .order_by()
        .values("service__project", "service__effort_rate")
        .annotate(Sum("hours"))
    )
    effort_cost_per_project = defaultdict(lambda: Z2)
    effort_hours_with_rate_undefined_per_project = defaultdict(lambda: Z1)
    hours_per_project = defaultdict(lambda: Z1)

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
        for row in Invoice.objects.invoiced()
        .filter(project__in=projects, invoiced_on__lte=cutoff_date)
        .order_by()
        .values("project")
        .annotate(Sum("total_excl_tax"))
    }

    statistics = [
        {
            "project": project,
            "logbook": cost_per_project.get(project.id, Z2)
            + effort_cost_per_project[project.id],
            "cost": cost_per_project.get(project.id, Z2),
            "effort_cost": effort_cost_per_project[project.id],
            "effort_hours_with_rate_undefined": effort_hours_with_rate_undefined_per_project[  # noqa
                project.id
            ],
            "third_party_costs": third_party_costs_per_project.get(project.id, Z2),
            "offered": offered_per_project.get(project.id, Z2),
            "invoiced": invoiced_per_project.get(project.id, Z2),
            "hours": hours_per_project[project.id],
            "not_archived": not_archived_hours.get(project.id, Z1),
            "delta": cost_per_project.get(project.id, Z2)
            + effort_cost_per_project[project.id]
            - invoiced_per_project.get(project.id, Z2),
        }
        for project in projects
    ]
    overall = {
        key: sum(s[key] for s in statistics)
        for key in [
            "logbook",
            "cost",
            "effort_cost",
            "effort_hours_with_rate_undefined",
            "third_party_costs",
            "offered",
            "invoiced",
            "hours",
            "not_archived",
        ]
    }
    overall["delta_positive"] = sum(s["delta"] for s in statistics if s["delta"] > 0)
    overall["delta_negative"] = sum(s["delta"] for s in statistics if s["delta"] < 0)

    return {
        "statistics": sorted(statistics, key=lambda s: s["delta"], reverse=True),
        "overall": overall,
    }
