import datetime as dt
from collections import defaultdict

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import BudgetTransfer, Service
from workbench.reporting.utils import effort_cost_by_project, sum_by
from workbench.tools.formats import Z1, Z2


def project_budget_statistics(projects, *, cutoff_date=None):
    cutoff_date = cutoff_date or dt.date.today()
    cutoff_dttm = timezone.make_aware(dt.datetime.combine(cutoff_date, dt.time.max))

    costs = LoggedCost.objects.filter(
        service__project__in=projects, rendered_on__lte=cutoff_dttm
    )
    cost_per_project = sum_by(costs, key="service__project", field="cost")
    third_party_costs_per_project = sum_by(
        costs.filter(third_party_costs__isnull=False, invoice_service__isnull=True),
        key="service__project",
        field="third_party_costs",
    )

    effort = effort_cost_by_project(
        LoggedHours.objects.filter(
            service__project__in=projects, rendered_on__lte=cutoff_dttm
        )
    )

    service_hours = sum_by(
        Service.objects.budgeted().filter(project__in=projects),
        key="project",
        field="service_hours",
        default=Z1,
    )

    sold_per_project = sum_by(
        Offer.objects.accepted().filter(project__in=projects, is_budget_retainer=False),
        key="project",
    )
    discount_per_project = sum_by(
        Offer.objects.not_declined().filter(
            project__in=projects, is_budget_retainer=False
        ),
        key="project",
        field="discount",
    )
    invoiced_per_project = sum_by(
        Invoice.objects.invoiced().filter(
            project__in=projects, invoiced_on__lte=cutoff_date
        ),
        key="project",
    )

    projected_gross_margin_on_cutoff_date = {}
    projected_gross_margin = defaultdict(lambda: Z2)
    for row in (
        ProjectedInvoice.objects
        .filter(project__in=projects, project__closed_on__isnull=True)
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

    # Budget which was invoiced on one project but is worked off on another
    # (or reserved for that) belongs to the project which does the work.
    budget_adjustments = BudgetTransfer.objects.adjustments(projects=projects)

    statistics = [
        {
            "project": project,
            "logbook": cost_per_project[project.id] + effort[project.id]["cost"],
            "cost": cost_per_project[project.id],
            "effort_cost": effort[project.id]["cost"],
            "effort_hours_with_rate_undefined": effort[project.id][
                "hours_rate_undefined"
            ],
            "third_party_costs": third_party_costs_per_project[project.id],
            "sold": sold_per_project[project.id] + budget_adjustments[project.id],
            "discount": Z2 - discount_per_project[project.id],
            "invoiced": invoiced_per_project[project.id],
            "hours": effort[project.id]["hours"],
            "service_hours": service_hours[project.id],
            "delta": cost_per_project[project.id]
            + effort[project.id]["cost"]
            - invoiced_per_project[project.id],
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
            "discount",
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
