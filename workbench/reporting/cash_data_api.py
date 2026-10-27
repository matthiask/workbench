import datetime as dt
from collections import defaultdict

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.reporting.api import has_valid_token, jsonable
from workbench.reporting.key_data import projected_gross_margin
from workbench.reporting.key_data_api import accruals
from workbench.reporting.utils import sum_by
from workbench.tools.formats import Z2


PLANNED_INVOICING_MONTHS = 7


def open_invoices_totals(invoices, cutoff_date):
    totals = {"total_excl_tax": Z2, "total_incl_tax": Z2, "overdue_incl_tax": Z2}
    for invoice in invoices:
        totals["total_excl_tax"] += invoice.total_excl_tax
        totals["total_incl_tax"] += invoice.total
        if invoice.due_on and invoice.due_on < cutoff_date:
            totals["overdue_incl_tax"] += invoice.total
    return totals


def receivables_by_due_week(invoices):
    weeks = defaultdict(lambda: {"amount_excl_tax": Z2, "amount_incl_tax": Z2})
    for invoice in invoices:
        # Invoices without due date are treated as due on the invoice date
        iso_year, iso_week, _weekday = (
            invoice.due_on or invoice.invoiced_on
        ).isocalendar()
        weeks[(iso_year, iso_week)]["amount_excl_tax"] += invoice.total_excl_tax
        weeks[(iso_year, iso_week)]["amount_incl_tax"] += invoice.total
    return [
        {"iso_year": year, "iso_week": week} | amounts
        for (year, week), amounts in sorted(weeks.items())
        if amounts["amount_excl_tax"] or amounts["amount_incl_tax"]
    ]


def planned_invoicing(cutoff_date, pgm):
    """
    Projected gross margin not yet invoiced per month, starting with the month
    of the cutoff date. Same values as in the key data report.
    """
    this = (cutoff_date.year, cutoff_date.month)
    months = [this]
    while len(months) < PLANNED_INVOICING_MONTHS or months[-1] < max(
        pgm["monthly_overall"], default=this
    ):
        year, month = months[-1]
        months.append((year + 1, 1) if month == 12 else (year, month + 1))
    return [
        {
            "month": "{}-{:02}".format(*month),
            "amount_excl_tax": pgm["monthly_overall"].get(month, Z2),
        }
        for month in months
    ]


def planned_invoicing_overdue(cutoff_date, pgm):
    """
    Projected gross margin of months before the cutoff date which hasn't been
    invoiced yet. The key data report shows it in the original month.
    """
    this = (cutoff_date.year, cutoff_date.month)
    return sum(
        (amount for month, amount in pgm["monthly_overall"].items() if month < this),
        Z2,
    )


def accepted_offers_not_invoiced(pgm):
    """
    Accepted offers of open projects minus everything invoiced on those
    projects already. The part not in planned invoicing is what remains after
    deducting the project's projected gross margin which hasn't been invoiced
    yet.
    """
    projects = Project.objects.open()
    offered = sum_by(
        Offer.objects.accepted().filter(project__in=projects), key="project"
    )
    invoiced = sum_by(
        Invoice.objects.invoiced().filter(project__in=offered.keys()), key="project"
    )
    planned = {row["project"].id: row["delta"] for row in pgm["projects"]}

    totals = {"total_excl_tax": Z2, "not_in_planned_invoicing_excl_tax": Z2}
    for project, total in offered.items():
        remaining = max(total - invoiced[project], Z2)
        totals["total_excl_tax"] += remaining
        totals["not_in_planned_invoicing_excl_tax"] += max(
            remaining - planned.get(project, Z2), Z2
        )
    return totals


def cash_data(date):
    """
    Dates in the current week are evaluated at the time of the request so that
    invoices paid since monday do not show up as open anymore. Projections and
    offers aren't versioned; they are only available for the current week.
    """
    today = dt.date.today()
    is_current = date >= today - dt.timedelta(days=today.weekday())
    cutoff_date = max(date, today) if is_current else date

    invoices = list(Invoice.objects.outstanding(on=cutoff_date).order_by("due_on"))
    data = {
        "date": date,
        "generated_at": timezone.localtime().isoformat(timespec="seconds"),
        "currency": "CHF",
        "open_invoices": open_invoices_totals(invoices, cutoff_date),
        "receivables_by_due_week": receivables_by_due_week(invoices),
        "accruals": accruals(cutoff_date),
        "planned_invoicing_by_month": None,
        "planned_invoicing_overdue_excl_tax": None,
        "accepted_offers_not_invoiced": None,
    }
    if is_current:
        pgm = projected_gross_margin()
        data["planned_invoicing_by_month"] = planned_invoicing(date, pgm)
        data["planned_invoicing_overdue_excl_tax"] = planned_invoicing_overdue(
            date, pgm
        )
        data["accepted_offers_not_invoiced"] = accepted_offers_not_invoiced(pgm)
    return data


@require_GET
def cash_data_api(request):
    if not has_valid_token(request):
        return HttpResponseForbidden()

    try:
        cutoff_date = dt.date.fromisoformat(
            request.GET.get("date") or dt.date.today().isoformat()
        )
    except ValueError:
        return HttpResponseBadRequest("Invalid date")
    return JsonResponse(jsonable(cash_data(cutoff_date)))
