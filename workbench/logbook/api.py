import datetime as dt
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from ninja import Query, Router, Schema
from ninja.pagination import paginate

from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.api import ProjectSummary, project_summary
from workbench.tools.api import (
    DateRangeFilter,
    Serialized,
    TotalsPagination,
    filter_date_range,
)
from workbench.tools.formats import Z1, Z2


# Read-only on purpose: The warnings of the logbook forms are useful
router = Router(tags=["logbook"])


class LoggedHoursOut(Schema):
    id: int
    url: str
    rendered_on: dt.date
    rendered_by: str
    hours: Decimal
    description: str
    project: ProjectSummary
    service_id: int
    service: str


class LoggedHoursPagination(TotalsPagination):
    class Output(Schema):
        items: list[Any]
        count: int
        total_hours: Decimal


class LoggedHoursFilter(DateRangeFilter):
    q: str = ""
    project: int | None = None
    customer: int | None = None
    offer: int | None = None
    service: int | None = None
    rendered_by: str | None = None


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
        queryset = queryset.filter(rendered_by___short_name__iexact=filters.rendered_by)
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
    }


@router.get("/logbook/hours/", response=list[LoggedHoursOut])
@paginate(LoggedHoursPagination)
def logged_hours_list(request, filters: Query[LoggedHoursFilter]):
    """Logged hours, newest first; the total includes all matching entries"""
    hours = _filter(LoggedHours.objects.all(), filters)
    return Serialized(
        hours.select_related("rendered_by", "service__project").order_by(
            "-rendered_on", "-created_at", "-pk"
        ),
        lambda row: _entry_out(row, request) | {"hours": row.hours},
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
        costs.select_related("rendered_by", "service__project").order_by(
            "-rendered_on", "-created_at", "-pk"
        ),
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
