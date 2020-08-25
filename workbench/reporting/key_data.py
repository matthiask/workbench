import datetime as dt
from collections import defaultdict
from itertools import chain

from django.db.models import Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear

from workbench.awt.reporting import full_time_equivalents_by_month
from workbench.invoices.models import Invoice
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

    months = sorted(set(chain.from_iterable([gross, third, accruals])))
    profit = []
    for month in months:
        date = dt.date(month[0], month[1], 1)
        row = {
            "month": month,
            "key": "%s-%s" % month,
            "date": date,
            "gross_profit": gross[month],
            "third_party_costs": third[month],
            "accruals": accruals.get(month) or {"accrual": None, "delta": Z2},
            "fte": fte.get(date, Z2),
        }
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
