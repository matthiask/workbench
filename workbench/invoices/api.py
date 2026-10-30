import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db.models import F
from django.shortcuts import get_object_or_404
from ninja import Query, Router, Schema

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.contacts.api import (
    OrganizationOut,
    PersonSummary,
    organization_out,
    person_summary,
)
from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.projects.api import ProjectSummary, project_summary
from workbench.projects.models import Project
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


class InvoiceFilter(Schema):
    q: str = ""
    project: int | None = None
    customer: int | None = None
    status: Literal["in_preparation", "sent", "paid", "canceled"] | None = None
    open: bool = False
    overdue: bool = False
    invoiced_since: dt.date | None = None


@router.get("/invoices/", response=list[InvoiceOut])
def invoice_list(request, filters: Query[InvoiceFilter]):
    """Invoices, newest first, at most 200

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
    if filters.invoiced_since:
        invoices = invoices.filter(invoiced_on__gte=filters.invoiced_since)
    if filters.q:
        invoices = invoices.search(filters.q)
    return [
        invoice_out(invoice, request)
        for invoice in invoices.order_by("-invoiced_on", "-pk")[:200]
    ]


class ReminderInvoiceOut(InvoiceOut):
    last_reminded_on: dt.date | None
    days_overdue: int


class Reminders(Schema):
    customer: OrganizationOut
    contact: PersonSummary | None
    total_excl_tax: Decimal
    total: Decimal
    invoices: list[ReminderInvoiceOut]


# The web interface's reminders aren't restricted either
@router.get("/invoices/reminders/", response=list[Reminders], auth=user_auth())
def reminders(request):
    """Invoices overdue for more than 15 days whose reminders haven't been
    postponed, per customer and contact; contacts reminded longest ago
    first"""
    invoices = (
        Invoice.objects
        .overdue()
        .select_related("customer", "contact__organization", "owned_by", "project")
        .order_by(F("last_reminded_on").asc(nulls_first=True), "invoiced_on")
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


@router.get(
    "/projects/{project_id}/projected-invoices/", response=list[ProjectedInvoiceOut]
)
def projected_invoice_list(request, project_id: int):
    """Planned invoicing of the project (gross margin, third party costs are
    not included)"""
    project = get_object_or_404(Project, pk=project_id)
    return [
        _projected_invoice_out(row, request)
        for row in ProjectedInvoice.objects.filter(project=project).select_related(
            "project"
        )
    ]


class ProjectedInvoiceFilter(Schema):
    project: int | None = None
    customer: int | None = None
    invoiced_since: dt.date | None = None
    invoiced_until: dt.date | None = None


@router.get("/projected-invoices/", response=list[ProjectedInvoiceOut])
def projected_invoice_list_search(request, filters: Query[ProjectedInvoiceFilter]):
    """Planned invoicing of all projects, oldest first, at most 200"""
    projected = ProjectedInvoice.objects.select_related("project")
    if filters.project:
        projected = projected.filter(project=filters.project)
    if filters.customer:
        projected = projected.filter(project__customer=filters.customer)
    if filters.invoiced_since:
        projected = projected.filter(invoiced_on__gte=filters.invoiced_since)
    if filters.invoiced_until:
        projected = projected.filter(invoiced_on__lte=filters.invoiced_until)
    return [
        _projected_invoice_out(row, request)
        for row in projected.order_by("invoiced_on", "pk")[:200]
    ]
