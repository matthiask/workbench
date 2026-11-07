import datetime as dt
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from ninja import Field, Query, Router, Schema
from ninja.pagination import paginate

from workbench.api_keys import InvoiceStatus, key
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.api import ProjectSummary, project_summary
from workbench.tools.api import (
    DateRangeFilter,
    OrganizationID,
    ProjectID,
    SearchQuery,
    Serialized,
    ShortName,
    TotalsPagination,
    filter_date_range,
    user_by_short_name,
)
from workbench.tools.formats import Z1, Z2


# Read-only on purpose: The warnings of the logbook forms are useful
router = Router(tags=["logbook"])


class InvoiceSummary(Schema):
    id: int
    code: str
    status: InvoiceStatus


class LoggedHoursOut(Schema):
    id: int
    url: str
    rendered_on: dt.date
    rendered_by: str
    hours: Decimal
    hours_for_invoicing: Decimal | None = Field(
        description="If set, the work is valued and invoiced with these hours"
        " instead of the hours, e.g. if it's worth more than the time spent."
    )
    description: str
    project: ProjectSummary
    service_id: int
    service: str
    archived_at: dt.datetime | None
    invoice: InvoiceSummary | None = Field(
        description="The invoice which contains the entry, if any."
    )


class LoggedHoursPagination(TotalsPagination):
    class Output(Schema):
        items: list[Any]
        count: int
        total_hours: Decimal


class LoggedHoursFilter(DateRangeFilter):
    q: SearchQuery = ""
    project: ProjectID = None
    customer: OrganizationID = None
    offer: int | None = None
    service: int | None = None
    rendered_by: ShortName = None
    invoiced: bool | None = Field(
        default=None, description="Only entries which are (not) on an invoice"
    )


class LoggedHoursListFilter(LoggedHoursFilter):
    hours_for_invoicing: bool = Field(
        default=False,
        description="Only entries with hours for invoicing, for sanity checks",
    )


def _filter(queryset, filters):
    if filters.project:
        queryset = queryset.filter(service__project=filters.project)
    if filters.customer:
        queryset = queryset.filter(service__project__customer=filters.customer)
    if filters.offer:
        queryset = queryset.filter(service__offer=filters.offer)
    if filters.service:
        queryset = queryset.filter(service=filters.service)
    if filters.rendered_by:
        queryset = queryset.filter(
            rendered_by=user_by_short_name(filters.rendered_by, param="rendered_by")
        )
    if filters.invoiced is not None:
        queryset = queryset.filter(invoice_service__isnull=not filters.invoiced)
    queryset = filter_date_range(queryset, filters, "rendered_on")
    if filters.q:
        queryset = queryset.search(filters.q)
    return queryset


def _entry_out(entry, request):
    return {
        "id": entry.id,
        "url": request.build_absolute_uri(entry.get_absolute_url()),
        "rendered_on": entry.rendered_on,
        "rendered_by": entry.rendered_by.get_short_name(),
        "description": entry.description,
        "project": project_summary(entry.service.project, request),
        "service_id": entry.service_id,
        "service": entry.service.title,
        "archived_at": entry.archived_at,
        "invoice": {
            "id": invoice.id,
            "code": invoice.code,
            "status": key("invoice_status", invoice.status),
        }
        if (invoice := entry.invoice_service and entry.invoice_service.invoice)
        else None,
    }


@router.get("/logbook/hours/", response=list[LoggedHoursOut])
@paginate(LoggedHoursPagination)
def logged_hours_list(request, filters: Query[LoggedHoursListFilter]):
    """Logged hours, newest first; the total includes all matching entries"""
    hours = _filter(LoggedHours.objects.all(), filters)
    if filters.hours_for_invoicing:
        hours = hours.filter(hours_for_invoicing__isnull=False)
    return Serialized(
        hours.select_related(
            "rendered_by", "service__project", "invoice_service__invoice__project"
        ).order_by("-rendered_on", "-created_at", "-pk"),
        lambda row: (
            _entry_out(row, request)
            | {"hours": row.hours, "hours_for_invoicing": row.hours_for_invoicing}
        ),
        totals={
            "total_hours": hours.order_by().aggregate(Sum("hours"))["hours__sum"] or Z1
        },
    )


class LoggedCostOut(Schema):
    id: int
    url: str
    rendered_on: dt.date
    rendered_by: str
    cost: Decimal
    third_party_costs: Decimal | None
    are_expenses: bool
    description: str
    project: ProjectSummary
    service_id: int
    service: str
    archived_at: dt.datetime | None
    invoice: InvoiceSummary | None = Field(
        description="The invoice which contains the entry, if any."
    )


class LoggedCostPagination(TotalsPagination):
    class Output(Schema):
        items: list[Any]
        count: int
        total_cost: Decimal
        total_third_party_costs: Decimal


class LoggedCostFilter(LoggedHoursFilter):
    expenses: bool = False


@router.get("/logbook/costs/", response=list[LoggedCostOut])
@paginate(LoggedCostPagination)
def logged_cost_list(request, filters: Query[LoggedCostFilter]):
    """Logged costs, newest first; the totals include all matching entries

    ``expenses`` are costs paid from someone's own pocket."""
    costs = _filter(LoggedCost.objects.all(), filters)
    if filters.expenses:
        costs = costs.filter(are_expenses=True)
    totals = costs.order_by().aggregate(
        cost=Sum("cost"), third_party_costs=Sum("third_party_costs")
    )
    return Serialized(
        costs.select_related(
            "rendered_by", "service__project", "invoice_service__invoice__project"
        ).order_by("-rendered_on", "-created_at", "-pk"),
        lambda row: (
            _entry_out(row, request)
            | {
                "cost": row.cost,
                "third_party_costs": row.third_party_costs,
                "are_expenses": row.are_expenses,
            }
        ),
        totals={
            "total_cost": totals["cost"] or Z2,
            "total_third_party_costs": totals["third_party_costs"] or Z2,
        },
    )
