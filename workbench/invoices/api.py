import datetime as dt
from decimal import Decimal
from typing import Literal

from django.shortcuts import get_object_or_404
from ninja import Query, Router, Schema

from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.projects.models import Project


router = Router(tags=["invoices"])

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
    project: str | None
    customer: str
    owned_by: str
    invoiced_on: dt.date | None
    due_on: dt.date | None
    closed_on: dt.date | None
    service_period_from: dt.date | None
    service_period_until: dt.date | None
    total_excl_tax: Decimal
    total: Decimal
    third_party_costs: Decimal | None


def _invoice_out(invoice, request):
    return {
        "id": invoice.id,
        "code": invoice.code,
        "url": request.build_absolute_uri(invoice.get_absolute_url()),
        "title": invoice.title,
        "description": invoice.description,
        "type": invoice.get_type_display(),
        "status": invoice.get_status_display(),
        "project": invoice.project.code if invoice.project else None,
        "customer": invoice.customer.name,
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
    return [
        _invoice_out(invoice, request)
        for invoice in invoices.order_by("-invoiced_on", "-pk")[:200]
    ]


@router.get("/invoices/{invoice_id}/", response=InvoiceOut)
def invoice_detail(request, invoice_id: int):
    return _invoice_out(
        get_object_or_404(
            Invoice.objects.select_related("project", "customer", "owned_by"),
            pk=invoice_id,
        ),
        request,
    )


class ProjectedInvoiceOut(Schema):
    invoiced_on: dt.date
    gross_margin: Decimal
    description: str


@router.get(
    "/projects/{project_id}/projected-invoices/", response=list[ProjectedInvoiceOut]
)
def projected_invoice_list(request, project_id: int):
    """Planned invoicing of the project (gross margin, third party costs are
    not included)"""
    project = get_object_or_404(Project, pk=project_id)
    return ProjectedInvoice.objects.filter(project=project)
