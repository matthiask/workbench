import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db.models import Q
from ninja import Query, Router, Schema

from workbench.awt.models import Absence


router = Router(tags=["absences"])


class AbsenceOut(Schema):
    id: int
    url: str
    user: str
    starts_on: dt.date
    ends_on: dt.date | None
    days: Decimal
    reason: str
    description: str


class AbsenceFilter(Schema):
    user: str | None = None
    reason: (
        Literal["vacation", "sickness", "paid", "school", "other", "correction"] | None
    ) = None
    since: dt.date | None = None
    until: dt.date | None = None


@router.get("/absences/", response=list[AbsenceOut])
def absence_list(request, filters: Query[AbsenceFilter]):
    """Absences overlapping the period from ``since`` until ``until``, oldest
    first, at most 500"""
    absences = Absence.objects.select_related("user")
    if filters.user:
        absences = absences.filter(user___short_name__iexact=filters.user)
    if filters.reason:
        absences = absences.filter(reason=filters.reason)
    if filters.since:
        absences = absences.filter(
            Q(ends_on__gte=filters.since)
            | Q(ends_on__isnull=True, starts_on__gte=filters.since)
        )
    if filters.until:
        absences = absences.filter(starts_on__lte=filters.until)
    return [
        {
            "id": absence.id,
            "url": request.build_absolute_uri(absence.get_absolute_url()),
            "user": absence.user.get_short_name(),
            "starts_on": absence.starts_on,
            "ends_on": absence.ends_on,
            "days": absence.days,
            "reason": absence.get_reason_display(),
            "description": absence.description,
        }
        for absence in absences.order_by("starts_on", "pk")[:500]
    ]
