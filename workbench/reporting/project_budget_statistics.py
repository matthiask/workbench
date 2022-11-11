import datetime as dt
from collections import defaultdict

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import Service
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

    service_hours = {
        row["project"]: row["service_hours__sum"]
        for row in Service.objects.budgeted()
        .filter(project__in=projects)
        .order_by()
        .values("project")
        .annotate(Sum("service_hours"))
    }

    sold_per_project = {
        row["project"]: row["total_excl_tax__sum"]
        for row in Offer.objects.accepted()
        .filter(project__in=projects, is_budget_retainer=False)
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

    projected_gross_margin_on_cutoff_date = {}
    projected_gross_margin = defaultdict(lambda: Z2)
    for row in (
        ProjectedInvoice.objects.filter(
            project__in=projects, project__closed_on__isnull=True
        )
        .annotate(
            before_cutoff_date=models.ExpressionWrapper(
                models.Q(invoiced_on__lte=cutoff_date),
                output_field=models.BooleanField(),
            )
        )
        .order_by()
        .values("project", "before_cutoff_date")
        .annotate(Sum("gross_margin"))
    ):
        if row["before_cutoff_date"]:
            projected_gross_margin_on_cutoff_date[row["project"]] = row[
                "gross_margin__sum"
            ]
        projected_gross_margin[row["project"]] += row["gross_margin__sum"]

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
            "sold": sold_per_project.get(project.id, Z2),
            "invoiced": invoiced_per_project.get(project.id, Z2),
            "hours": hours_per_project[project.id],
            "service_hours": service_hours.get(project.id, Z1),
            "delta": cost_per_project.get(project.id, Z2)
            + effort_cost_per_project[project.id]
            - invoiced_per_project.get(project.id, Z2),
            "projected_gross_margin": projected_gross_margin[project.id],
            "projected_gross_margin_on_cutoff_date": projected_gross_margin_on_cutoff_date.get(
                project.id, Z2
            ),
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
            "sold",
            "invoiced",
            "hours",
            "service_hours",
            "projected_gross_margin",
            "projected_gross_margin_on_cutoff_date",
        ]
    }
    overall["delta_positive"] = sum(s["delta"] for s in statistics if s["delta"] > 0)
    overall["delta_negative"] = sum(s["delta"] for s in statistics if s["delta"] < 0)

    return {
        "statistics": sorted(statistics, key=lambda s: s["delta"], reverse=True),
        "overall": overall,
        "cutoff_date": cutoff_date,
    }
