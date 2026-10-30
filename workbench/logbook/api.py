import datetime as dt
from decimal import Decimal

from django.db.models import Count, Sum
from ninja import Query, Router, Schema

from workbench.logbook.models import LoggedHours
from workbench.tools.formats import Z1


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


@router.get("/logbook/hours/", response=LoggedHoursList)
def logged_hours_list(request, filters: Query[LoggedHoursFilter]):
    """Logged hours, newest first, at most 500; the total and the count
    include all matching entries"""
    hours = LoggedHours.objects.all()
    if filters.project:
        hours = hours.filter(service__project=filters.project)
    if filters.customer:
        hours = hours.filter(service__project__customer=filters.customer)
    if filters.offer:
        hours = hours.filter(service__offer=filters.offer)
    if filters.service:
        hours = hours.filter(service=filters.service)
    if filters.rendered_by:
        hours = hours.filter(rendered_by___short_name__iexact=filters.rendered_by)
    if filters.rendered_since:
        hours = hours.filter(rendered_on__gte=filters.rendered_since)
    if filters.rendered_until:
        hours = hours.filter(rendered_on__lte=filters.rendered_until)
    if filters.q:
        hours = hours.search(filters.q)
    totals = hours.order_by().aggregate(hours=Sum("hours"), count=Count("id"))
    return {
        "total_hours": totals["hours"] or Z1,
        "count": totals["count"],
        "hours": [
            {
                "id": row.id,
                "url": request.build_absolute_uri(row.get_absolute_url()),
                "rendered_on": row.rendered_on,
                "rendered_by": row.rendered_by.get_short_name(),
                "hours": row.hours,
                "description": row.description,
                "project_id": row.service.project_id,
                "project": row.service.project.code,
                "service_id": row.service_id,
                "service": row.service.title,
            }
            for row in hours.select_related("rendered_by", "service__project")[:500]
        ],
    }
