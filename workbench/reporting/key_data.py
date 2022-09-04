import datetime as dt
from collections import defaultdict
from itertools import takewhile

from django.db.models import Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear

from workbench.awt.reporting import full_time_equivalents_by_month
from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service
from workbench.reporting.models import Accruals
from workbench.tools.formats import Z1, Z2


def gross_profit_by_month(date_range):
    profit = defaultdict(lambda: Z2)
    for result in (
        Invoice.objects.invoiced()
        .order_by()
        .filter(invoiced_on__range=date_range)
        .annotate(year=ExtractYear("invoiced_on"), month=ExtractMonth("invoiced_on"))
        .values("year", "month")
        .annotate(Sum("total_excl_tax"))
    ):
        profit[(result["year"], result["month"])] += result["total_excl_tax__sum"]
    return profit


def third_party_costs_by_month(date_range):
    costs = defaultdict(lambda: Z2)

    for result in (
        LoggedCost.objects.filter(
            rendered_on__range=date_range,
            third_party_costs__isnull=False,
            invoice_service__isnull=True,
        )
        .order_by()
        .annotate(year=ExtractYear("rendered_on"), month=ExtractMonth("rendered_on"))
        .values("year", "month")
        .annotate(Sum("third_party_costs"))
    ):
        costs[(result["year"], result["month"])] -= result["third_party_costs__sum"]

    for result in (
        Invoice.objects.invoiced()
        .filter(~Q(type=Invoice.DOWN_PAYMENT))
        .order_by()
        .filter(Q(invoiced_on__range=date_range), ~Q(third_party_costs=Z2))
        .annotate(year=ExtractYear("invoiced_on"), month=ExtractMonth("invoiced_on"))
        .values("year", "month")
        .annotate(Sum("third_party_costs"))
    ):
        costs[(result["year"], result["month"])] -= result["third_party_costs__sum"]

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

    dates = list(sorted(accruals))
    for this, next in zip(dates, dates[1:]):
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

    pi = projected_invoices()

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
            "key": "%s-%s" % month,
            "date": day,
            "gross_profit": gross[month],
            "third_party_costs": third[month],
            "accruals": accruals.get(month) or {"accrual": None, "delta": Z2},
            "fte": fte.get(day, Z2),
            "projected_invoices": pi["monthly_overall"].get(month),
        }
        if not any(
            (
                row["gross_profit"],
                row["third_party_costs"],
                row["accruals"]["delta"],
                row["projected_invoices"],
            )
        ):
            continue

        row["gross_margin"] = (
            row["gross_profit"] + row["third_party_costs"] + row["accruals"]["delta"]
        )
        row["margin_per_fte"] = row["gross_margin"] / row["fte"] if row["fte"] else None
        profit.append(row)

    return profit


def service_hours_in_open_orders():
    return (
        Service.objects.budgeted()
        .filter(project__type=Project.ORDER, project__closed_on__isnull=True)
        .order_by()
        .aggregate(h=Sum("service_hours"))["h"]
        or Z1
    )


def projected_invoices():
    open_projects = Project.objects.open().select_related("owned_by")

    projected = ProjectedInvoice.objects.filter(
        project__in=open_projects
    ).select_related("project__owned_by")
    invoices = (
        Invoice.objects.invoiced()
        .filter(project__in=open_projects)
        .select_related("project__owned_by")
    )

    projects = defaultdict(lambda: {"projected": [], "invoiced": []})

    for pi in projected:
        projects[pi.project]["projected"].append(pi)
    for pi in invoices:
        projects[pi.project]["invoiced"].append(pi)

    for data in projects.values():
        data["projected_total"] = sum((pi.gross_margin for pi in data["projected"]), Z2)
        data["gross_margin"] = sum(
            (i.total_excl_tax - i.third_party_costs for i in data["invoiced"]), Z2
        )

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
        for project in projected_invoices()["projects"]:
            project["unsent"] = sum(
                (total for month, total in project["monthly"].items() if month < this),
                Z2,
            )
            if project["unsent"] > 0:
                yield project

    return _filter()


def logged_hours_in_open_orders():
    return (
        LoggedHours.objects.filter(
            service__project__type=Project.ORDER,
            service__project__closed_on__isnull=True,
        )
        .order_by()
        .aggregate(h=Sum("hours"))["h"]
        or Z1
    )


def sent_invoices_total():
    return (
        Invoice.objects.filter(status=Invoice.SENT)
        .order_by()
        .aggregate(t=Sum("total_excl_tax"))["t"]
        or Z2
    )


def open_offers_total():
    return (
        Offer.objects.offered().order_by().aggregate(t=Sum("total_excl_tax"))["t"] or Z2
    )
