import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.contacts.api import (
    OrganizationOut,
    PersonSummary,
    organization_out,
    person_summary,
)
from workbench.invoices.models import Invoice, ProjectedInvoice, RecurringInvoice
from workbench.projects.api import ProjectSummary, project_summary
from workbench.tools.api import DateRangeFilter, Serialized, filter_date_range
from workbench.tools.formats import Z2


# Same as in the web interface
router = Router(auth=user_auth(feature=FEATURES.CONTROLLING), tags=["invoices"])

STATUSES = {
    "in_preparation": Invoice.IN_PREPARATION,
    "sent": Invoice.SENT,
    "paid": Invoice.PAID,
    "canceled": Invoice.CANCELED,
}


class InvoiceOut(Schema):
    id: int
    code: str
    url: str
    title: str
    description: str
    type: str
    status: str
    project: ProjectSummary | None
    customer: OrganizationOut
    owned_by: str
    invoiced_on: dt.date | None
    due_on: dt.date | None
    closed_on: dt.date | None
    service_period_from: dt.date | None
    service_period_until: dt.date | None
    total_excl_tax: Decimal
    total: Decimal
    third_party_costs: Decimal | None


def invoice_out(invoice, request):
    return {
        "id": invoice.id,
        "code": invoice.code,
        "url": request.build_absolute_uri(invoice.get_absolute_url()),
        "title": invoice.title,
        "description": invoice.description,
        "type": invoice.get_type_display(),
        "status": invoice.get_status_display(),
        "project": project_summary(invoice.project, request)
        if invoice.project
        else None,
        "customer": organization_out(invoice.customer, request),
        "owned_by": invoice.owned_by.get_short_name(),
        "invoiced_on": invoice.invoiced_on,
        "due_on": invoice.due_on,
        "closed_on": invoice.closed_on,
        "service_period_from": invoice.service_period_from,
        "service_period_until": invoice.service_period_until,
        "total_excl_tax": invoice.total_excl_tax,
        "total": invoice.total,
        "third_party_costs": invoice.third_party_costs,
    }


class InvoiceFilter(DateRangeFilter):
    q: str = ""
    project: int | None = None
    customer: int | None = None
    status: Literal["in_preparation", "sent", "paid", "canceled"] | None = None
    open: bool = False
    overdue: bool = False


@router.get("/invoices/", response=list[InvoiceOut])
@paginate
def invoice_list(request, filters: Query[InvoiceFilter]):
    """Invoices, newest first; the period filters the invoice date

    ``open`` are invoices in preparation or sent, ``overdue`` invoices sent and
    due for more than 15 days (as for reminders)."""
    invoices = Invoice.objects.select_related("project", "customer", "owned_by")
    if filters.project:
        invoices = invoices.filter(project=filters.project)
    if filters.customer:
        invoices = invoices.filter(customer=filters.customer)
    if filters.status:
        invoices = invoices.filter(status=STATUSES[filters.status])
    if filters.open:
        invoices = invoices.open()
    if filters.overdue:
        invoices = invoices.overdue()
    invoices = filter_date_range(invoices, filters, "invoiced_on")
    if filters.q:
        invoices = invoices.search(filters.q)
    return Serialized(
        invoices.order_by("-invoiced_on", "-pk"),
        lambda invoice: invoice_out(invoice, request),
    )


class ReminderInvoiceOut(InvoiceOut):
    last_reminded_on: dt.date | None
    days_overdue: int


class Reminders(Schema):
    customer: OrganizationOut
    contact: PersonSummary | None
    total_excl_tax: Decimal
    total: Decimal
    invoices: list[ReminderInvoiceOut]


def _overdue():
    return Invoice.objects.overdue().select_related(
        "customer", "contact__organization", "owned_by", "project"
    )


# The web interface's reminders aren't restricted either
@router.get("/invoices/reminders/", response=list[Reminders], auth=user_auth())
def reminders(request):
    """Invoices overdue for more than 15 days whose reminders haven't been
    postponed, per customer and contact; contacts reminded longest ago
    first"""
    return _reminders(_overdue(), request)


def _reminders(invoices, request):
    invoices = invoices.order_by(
        F("last_reminded_on").asc(nulls_first=True), "invoiced_on"
    )
    today = dt.date.today()
    nested = {}
    for invoice in invoices:
        row = nested.setdefault(
            (invoice.customer, invoice.contact),
            {
                "customer": organization_out(invoice.customer, request),
                "contact": person_summary(invoice.contact, request)
                if invoice.contact
                else None,
                "total_excl_tax": Z2,
                "total": Z2,
                "invoices": [],
            },
        )
        row["total_excl_tax"] += invoice.total_excl_tax
        row["total"] += invoice.total
        row["invoices"].append(
            invoice_out(invoice, request)
            | {
                "last_reminded_on": invoice.last_reminded_on,
                "days_overdue": (today - invoice.due_on).days,
            }
        )
    return list(nested.values())


class Reminded(Schema):
    invoices: list[int] = Field(
        min_length=1, description="IDs of overdue invoices from the reminders."
    )


@router.post("/invoices/reminders/", response=list[Reminders], auth=user_auth())
def mark_reminded(request, data: Reminded, *, dry_run: bool = False):
    """Mark invoices as reminded today like in the web interface, e.g. after
    sending a dunning letter; returns these invoices with their reminders"""
    invoices = _overdue().filter(id__in=data.invoices)
    if unknown := sorted(set(data.invoices) - {invoice.id for invoice in invoices}):
        raise ValidationError([
            {
                "loc": ["body", "data", "invoices"],
                "msg": _("These invoices aren't overdue: %s")
                % ", ".join(map(str, unknown)),
            }
        ])
    with transaction.atomic():
        invoices.update(last_reminded_on=dt.date.today())
        result = _reminders(_overdue().filter(id__in=data.invoices), request)
        if dry_run:
            transaction.set_rollback(True)
    return result


@router.get("/invoices/{invoice_id}/", response=InvoiceOut)
def invoice_detail(request, invoice_id: int):
    return invoice_out(
        get_object_or_404(
            Invoice.objects.select_related("project", "customer", "owned_by"),
            pk=invoice_id,
        ),
        request,
    )


class ProjectedInvoiceOut(Schema):
    project: ProjectSummary
    invoiced_on: dt.date
    gross_margin: Decimal
    description: str


def _projected_invoice_out(projected_invoice, request):
    return {
        "project": project_summary(projected_invoice.project, request),
        "invoiced_on": projected_invoice.invoiced_on,
        "gross_margin": projected_invoice.gross_margin,
        "description": projected_invoice.description,
    }


class ProjectedInvoiceFilter(DateRangeFilter):
    project: int | None = None
    customer: int | None = None


@router.get("/projected-invoices/", response=list[ProjectedInvoiceOut])
@paginate
def projected_invoice_list_search(request, filters: Query[ProjectedInvoiceFilter]):
    """Planned invoicing (gross margin, third party costs are not included),
    oldest first; the period filters the planned invoice date"""
    projected = ProjectedInvoice.objects.select_related("project")
    if filters.project:
        projected = projected.filter(project=filters.project)
    if filters.customer:
        projected = projected.filter(project__customer=filters.customer)
    projected = filter_date_range(projected, filters, "invoiced_on")
    return Serialized(
        projected.order_by("invoiced_on", "pk"),
        lambda row: _projected_invoice_out(row, request),
    )


class RecurringInvoiceOut(Schema):
    id: int
    url: str
    title: str
    description: str
    customer: OrganizationOut
    owned_by: str
    periodicity: str
    starts_on: dt.date
    ends_on: dt.date | None
    next_period_starts_on: dt.date | None
    total_excl_tax: Decimal
    total: Decimal
    third_party_costs: Decimal


class RecurringInvoiceFilter(Schema):
    q: str = ""
    customer: int | None = None
    owned_by: str | None = None
    status: Literal["open", "closed", "all"] = "open"


@router.get("/recurring-invoices/", response=list[RecurringInvoiceOut])
@paginate
def recurring_invoice_list(request, filters: Query[RecurringInvoiceFilter]):
    """Recurring invoices by customer, open ones by default (those whose
    auto-renewal hasn't been canceled before today)"""
    invoices = RecurringInvoice.objects.select_related("customer", "owned_by")
    if filters.status == "open":
        invoices = invoices.open()
    elif filters.status == "closed":
        invoices = invoices.closed()
    if filters.customer:
        invoices = invoices.filter(customer=filters.customer)
    if filters.owned_by:
        invoices = invoices.filter(owned_by___short_name__iexact=filters.owned_by)
    if filters.q:
        invoices = invoices.search(filters.q)
    return Serialized(
        invoices.order_by("customer__name", "title", "pk"),
        lambda invoice: {
            "id": invoice.id,
            "url": request.build_absolute_uri(invoice.get_absolute_url()),
            "title": invoice.title,
            "description": invoice.description,
            "customer": organization_out(invoice.customer, request),
            "owned_by": invoice.owned_by.get_short_name(),
            "periodicity": invoice.get_periodicity_display(),
            "starts_on": invoice.starts_on,
            "ends_on": invoice.ends_on,
            "next_period_starts_on": invoice.next_period_starts_on,
            "total_excl_tax": invoice.total_excl_tax,
            "total": invoice.total,
            "third_party_costs": invoice.third_party_costs,
        },
    )
