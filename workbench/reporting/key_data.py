import datetime as dt
from collections import defaultdict
from itertools import chain

from django.db import connections
from django.db.models import Sum
from django.db.models.functions import ExtractMonth, ExtractYear

from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost
from workbench.tools.models import Z


def gross_profit_by_month(date_range):
    profit = defaultdict(lambda: Z)
    for row in (
        Invoice.objects.valid()
        .order_by()
        .filter(invoiced_on__range=date_range)
        .annotate(year=ExtractYear("invoiced_on"), month=ExtractMonth("invoiced_on"))
        .values("year", "month")
        .annotate(Sum("subtotal"), Sum("discount"), Sum("down_payment_total"))
    ):
        profit[(row["year"], row["month"])] += (
            row["subtotal__sum"] - row["discount__sum"] - row["down_payment_total__sum"]
        )
    return profit


def third_party_costs_by_month(date_range):
    costs = defaultdict(lambda: Z)

    for row in (
        LoggedCost.objects.order_by()
        .filter(rendered_on__range=date_range)
        .filter(third_party_costs__isnull=False)
        .annotate(year=ExtractYear("rendered_on"), month=ExtractMonth("rendered_on"))
        .values("year", "month")
        .annotate(Sum("third_party_costs"))
    ):
        costs[(row["year"], row["month"])] += row["third_party_costs__sum"]

    return costs


def accruals_by_month(date_range):
    accruals = {(0, 0): {"accrual": Z, "delta": None}}
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """\
SELECT
    cutoff_date,
    SUM((i.subtotal - i.discount) * (100 - a.work_progress) / 100)
FROM accruals_accrual a
LEFT JOIN invoices_invoice i ON i.id=a.invoice_id
GROUP BY cutoff_date
ORDER BY cutoff_date
"""
        )

        for row in cursor:
            # Overwrite earlier accruals if a month has more than one cutoff date
            accruals[(row[0].year, row[0].month)] = {"accrual": -row[1], "delta": None}

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

    months = sorted(set(chain.from_iterable([gross, third, accruals])))
    profit = []
    for month in months:
        row = {
            "month": month,
            "date": dt.date(month[0], month[1], 1),
            "gross_profit": gross.get(month, Z),
            "third_party_costs": -third.get(month, Z),
            "accruals": accruals.get(month) or {"accrual": None, "delta": Z},
        }
        row["gross_margin"] = (
            row["gross_profit"] + row["third_party_costs"] + row["accruals"]["delta"]
        )
        profit.append(row)

    return profit
