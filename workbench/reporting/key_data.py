import datetime as dt
from collections import defaultdict
from itertools import chain

from django.db import connections
from django.db.models import Q, Sum

from workbench.accruals.models import Accrual
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.models import Project, Service
from workbench.tools.models import Z


def gross_profit_by_month(date_range):
    profit = defaultdict(lambda: {"total_excl_tax": Z, "invoices": []})
    for invoice in (
        Invoice.objects.valid()
        .filter(invoiced_on__range=date_range)
        .order_by("invoiced_on", "id")
        .select_related("project", "owned_by")
    ):
        row = profit[(invoice.invoiced_on.year, invoice.invoiced_on.month)]
        row["total_excl_tax"] += invoice.total_excl_tax
        row["invoices"].append(invoice)
    return profit


def third_party_costs_by_month(date_range):
    costs = defaultdict(
        lambda: {"third_party_costs": Z, "invoices": [], "logged_costs": []}
    )

    for cost in (
        LoggedCost.objects.filter(
            rendered_on__range=date_range,
            third_party_costs__isnull=False,
            invoice_service__isnull=True,
        )
        .order_by("rendered_on", "id")
        .select_related("service")
    ):
        row = costs[(cost.rendered_on.year, cost.rendered_on.month)]
        row["third_party_costs"] -= cost.third_party_costs
        row["logged_costs"].append(cost)

    for invoice in (
        Invoice.objects.valid()
        .filter(Q(invoiced_on__range=date_range), ~Q(third_party_costs=Z))
        .order_by("invoiced_on", "id")
        .select_related("project", "owned_by")
    ):
        row = costs[(invoice.invoiced_on.year, invoice.invoiced_on.month)]
        row["third_party_costs"] -= invoice.third_party_costs
        row["invoices"].append(invoice)

    return costs


def accruals_by_month(date_range):
    accruals = {(0, 0): {"accrual": Z, "delta": None}}
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """\
SELECT
    cutoff_date,
    SUM(i.total_excl_tax * (100 - a.work_progress) / 100)
FROM accruals_accrual a
LEFT JOIN invoices_invoice i ON i.id=a.invoice_id
GROUP BY cutoff_date
ORDER BY cutoff_date
"""
        )

        for row in cursor:
            # Overwrite earlier accruals if a month has more than one cutoff date
            accruals[(row[0].year, row[0].month)] = {"accrual": -row[1], "delta": None}

    today = dt.date.today()
    accruals[(today.year, today.month)] = {
        "accrual": -Accrual.objects.generate_accruals(cutoff_date=today, save=False),
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

    months = sorted(set(chain.from_iterable([gross, third, accruals])))
    profit = []
    for month in months:
        row = {
            "month": month,
            "key": "%s-%s" % month,
            "date": dt.date(month[0], month[1], 1),
            "gross_profit": gross[month],
            "third_party_costs": third[month],
            "accruals": accruals.get(month) or {"accrual": None, "delta": Z},
        }
        row["gross_margin"] = (
            row["gross_profit"]["total_excl_tax"]
            + row["third_party_costs"]["third_party_costs"]
            + row["accruals"]["delta"]
        )
        profit.append(row)

    return profit


def service_hours_in_open_orders():
    return (
        Service.objects.budgeted()
        .filter(project__type=Project.ORDER, project__closed_on__isnull=True,)
        .order_by()
        .aggregate(h=Sum("service_hours"))["h"]
        or Z
    )


def logged_hours_in_open_orders():
    return (
        LoggedHours.objects.filter(
            service__project__type=Project.ORDER,
            service__project__closed_on__isnull=True,
        )
        .order_by()
        .aggregate(h=Sum("hours"))["h"]
        or Z
    )


def sent_invoices_total():
    return (
        Invoice.objects.filter(status=Invoice.SENT)
        .order_by()
        .aggregate(t=Sum("total_excl_tax"))["t"]
        or Z
    )
