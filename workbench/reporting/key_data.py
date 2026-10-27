import datetime as dt
from collections import defaultdict
from itertools import pairwise, takewhile

from django.db.models import Q

from workbench.awt.reporting import full_time_equivalents_by_month
from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service
from workbench.reporting.models import Accruals
from workbench.reporting.squeeze import gross_margin_components
from workbench.reporting.utils import sum_by_month, sum_of
from workbench.tools.formats import Z1, Z2


def gross_profit_by_month(date_range):
    return sum_by_month(
        Invoice.objects.invoiced().filter(invoiced_on__range=date_range),
        date_field="invoiced_on",
    )


def third_party_costs_by_month(date_range):
    """Third party costs as negative amounts per month"""
    logged = sum_by_month(
        LoggedCost.objects.filter(
            rendered_on__range=date_range,
            third_party_costs__isnull=False,
            invoice_service__isnull=True,
        ),
        date_field="rendered_on",
        field="third_party_costs",
    )
    invoiced = sum_by_month(
        Invoice.objects
        .invoiced()
        .filter(~Q(type=Invoice.DOWN_PAYMENT))
        .filter(Q(invoiced_on__range=date_range), ~Q(third_party_costs=Z2)),
        date_field="invoiced_on",
        field="third_party_costs",
    )
    costs = defaultdict(lambda: Z2)
    for month in {*logged, *invoiced}:
        costs[month] -= logged[month] + invoiced[month]
    return costs


def accruals_by_month(date_range):
    accruals = {(0, 0): {"accrual": Z2, "delta": None}}
    for accrual in Accruals.objects.order_by("cutoff_date"):
        accruals[(accrual.cutoff_date.year, accrual.cutoff_date.month)] = {
            "accrual": accrual.accruals,
            "delta": None,
        }

    today = dt.date.today()
    accruals[(today.year, today.month)] = {
        "accrual": Accruals.objects.accruals(cutoff_date=today),
        "delta": None,
    }

    dates = sorted(accruals)
    for this, next in pairwise(dates):
        accruals[next]["delta"] = accruals[next]["accrual"] - accruals[this]["accrual"]

    return {
        month: accrual
        for month, accrual in accruals.items()
        if month != (0, 0)
        and date_range[0] <= dt.date(month[0], month[1], 1) <= date_range[1]
    }


def gross_margin_by_month(date_range):
    gross = gross_profit_by_month(date_range)
    third = third_party_costs_by_month(date_range)
    accruals = accruals_by_month(date_range)
    fte = full_time_equivalents_by_month()

    pgm = projected_gross_margin()

    first_of_months = list(
        takewhile(
            lambda day: day < date_range[1],
            recurring(date_range[0], "monthly"),
        )
    )

    profit = []
    for day in first_of_months:
        month = (day.year, day.month)
        row = {
            "month": month,
            "key": "{}-{}".format(*month),
            "date": day,
            "gross_profit": gross[month],
            "third_party_costs": third[month],
            "accruals": accruals.get(month) or {"accrual": None, "delta": Z2},
            "fte": fte.get(day, Z2),
            "projected_gross_margin": pgm["monthly_overall"].get(month),
        }
        if not any((
            row["gross_profit"],
            row["third_party_costs"],
            row["accruals"]["delta"],
            row["projected_gross_margin"],
        )):
            continue

        row["gross_margin"] = (
            row["gross_profit"] + row["third_party_costs"] + row["accruals"]["delta"]
        )
        row["margin_per_fte"] = row["gross_margin"] / row["fte"] if row["fte"] else None
        profit.append(row)

    return profit


def service_hours_in_open_orders():
    return sum_of(
        Service.objects.budgeted().filter(
            project__type=Project.ORDER, project__closed_on__isnull=True
        ),
        field="service_hours",
        default=Z1,
    )


def projected_gross_margin(projects=None):
    if projects is None:
        projects = Project.objects.open()
    open_projects = projects.select_related("owned_by")

    projected = ProjectedInvoice.objects.filter(
        project__in=open_projects
    ).select_related("project__owned_by")

    projects = defaultdict(lambda: {"projected": []})
    for pi in projected:
        projects[pi.project]["projected"].append(pi)

    gross_margins = gross_margin_components([project.id for project in projects])
    for project, data in projects.items():
        data["projected_total"] = gross_margins[project.id]["projected"]
        data["gross_margin"] = gross_margins[project.id]["invoiced"]

    monthly_overall = defaultdict(lambda: Z2)

    def _monthly(data):
        monthly = defaultdict(lambda: Z2)
        projected = sorted(
            data["projected"], key=lambda pi: pi.invoiced_on, reverse=True
        )
        delta = data["delta"]
        for pi in projected:
            month = (pi.invoiced_on.year, pi.invoiced_on.month)
            if (d := min(delta, pi.gross_margin)) > 0:
                monthly[month] += d
                monthly_overall[month] += d
            else:
                break
            delta -= pi.gross_margin
        data["monthly"] = dict(monthly)
        return data

    projects = [
        _monthly(
            {
                "project": project,
                "delta": data["projected_total"] - data["gross_margin"],
            }
            | data
        )
        for project, data in projects.items()
        if data["projected_total"] > data["gross_margin"]
    ]

    return {
        "projects": projects,
        "monthly_overall": monthly_overall,
    }


def unsent_projected_invoices(cutoff_date):
    this = (cutoff_date.year, cutoff_date.month)

    def _filter():
        for project in projected_gross_margin()["projects"]:
            project["unsent"] = sum(
                (total for month, total in project["monthly"].items() if month < this),
                Z2,
            )
            if project["unsent"] > 0:
                yield project

    return _filter()


def logged_hours_in_open_orders():
    return sum_of(
        LoggedHours.objects.filter(
            service__project__type=Project.ORDER,
            service__project__closed_on__isnull=True,
        ),
        field="hours",
        default=Z1,
    )


def sent_invoices_total():
    return sum_of(Invoice.objects.filter(status=Invoice.SENT))


def due_invoices_total():
    return sum_of(
        Invoice.objects.filter(status=Invoice.SENT, due_on__lte=dt.date.today())
    )


def open_offers_total():
    return sum_of(Offer.objects.offered())
