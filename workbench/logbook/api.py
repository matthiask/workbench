import datetime as dt
from decimal import Decimal

from django.db.models import Count, Sum
from ninja import Query, Router, Schema

from workbench.logbook.models import LoggedCost, LoggedHours
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
    project_id: int
    project: str
    service_id: int
    service: str


class LoggedHoursList(Schema):
    total_hours: Decimal
    count: int
    hours: list[LoggedHoursOut]


class LoggedHoursFilter(Schema):
    q: str = ""
    project: int | None = None
    customer: int | None = None
    offer: int | None = None
    service: int | None = None
    rendered_by: str | None = None
    rendered_since: dt.date | None = None
    rendered_until: dt.date | None = None


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
    if filters.rendered_since:
        queryset = queryset.filter(rendered_on__gte=filters.rendered_since)
    if filters.rendered_until:
        queryset = queryset.filter(rendered_on__lte=filters.rendered_until)
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
        "project_id": entry.service.project_id,
        "project": entry.service.project.code,
        "service_id": entry.service_id,
        "service": entry.service.title,
    }


@router.get("/logbook/hours/", response=LoggedHoursList)
def logged_hours_list(request, filters: Query[LoggedHoursFilter]):
    """Logged hours, newest first, at most 500; the total and the count
    include all matching entries"""
    hours = _filter(LoggedHours.objects.all(), filters)
    totals = hours.order_by().aggregate(hours=Sum("hours"), count=Count("id"))
    return {
        "total_hours": totals["hours"] or Z1,
        "count": totals["count"],
        "hours": [
            _entry_out(row, request) | {"hours": row.hours}
            for row in hours.select_related("rendered_by", "service__project")[:500]
        ],
    }


class LoggedCostOut(Schema):
    id: int
    url: str
    rendered_on: dt.date
    rendered_by: str
    cost: Decimal
    third_party_costs: Decimal | None
    are_expenses: bool
    description: str
    project_id: int
    project: str
    service_id: int
    service: str


class LoggedCostList(Schema):
    total_cost: Decimal
    total_third_party_costs: Decimal
    count: int
    costs: list[LoggedCostOut]


class LoggedCostFilter(LoggedHoursFilter):
    expenses: bool = False


@router.get("/logbook/costs/", response=LoggedCostList)
def logged_cost_list(request, filters: Query[LoggedCostFilter]):
    """Logged costs, newest first, at most 500; the totals and the count
    include all matching entries

    ``expenses`` are costs paid from someone's own pocket."""
    costs = _filter(LoggedCost.objects.all(), filters)
    if filters.expenses:
        costs = costs.filter(are_expenses=True)
    totals = costs.order_by().aggregate(
        cost=Sum("cost"),
        third_party_costs=Sum("third_party_costs"),
        count=Count("id"),
    )
    return {
        "total_cost": totals["cost"] or Z2,
        "total_third_party_costs": totals["third_party_costs"] or Z2,
        "count": totals["count"],
        "costs": [
            _entry_out(row, request)
            | {
                "cost": row.cost,
                "third_party_costs": row.third_party_costs,
                "are_expenses": row.are_expenses,
            }
            for row in costs.select_related("rendered_by", "service__project")[:500]
        ],
    }
