import datetime as dt
from decimal import Decimal
from typing import Literal

from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localdate, localtime, make_aware
from django.utils.translation import gettext as _
from ninja import Field, Router, Schema
from ninja.errors import ValidationError

from workbench.projects.api import ProjectSummary, project_summary
from workbench.timer.models import Timestamp
from workbench.tools.formats import Z1


router = Router(tags=["timer"])


class TimestampIn(Schema):
    type: Literal["start", "stop"]
    notes: str = Field(default="", max_length=500)
    time: dt.time | None = Field(
        default=None, description="Today at this time instead of now."
    )
    minutes: int | None = Field(
        default=None,
        description="Minutes relative to now instead of now, e.g. -5 for five"
        " minutes ago.",
    )


class TimestampOut(Schema):
    id: int
    type: str
    created_at: dt.datetime
    notes: str


@router.post("/timestamps/", response=TimestampOut)
def timestamp_create(request, data: TimestampIn):
    """Start or stop a task, like the timer in the web interface"""
    if data.time is not None and data.minutes is not None:
        raise ValidationError([
            {"loc": ["body", "data"], "msg": _("Pass either time or minutes.")}
        ])
    created_at = timezone.now()
    if data.time is not None:
        created_at = make_aware(dt.datetime.combine(localdate(), data.time))
    elif data.minutes is not None:
        created_at += dt.timedelta(minutes=data.minutes)
    timestamp = Timestamp.objects.create(
        user=request.user, type=data.type, notes=data.notes, created_at=created_at
    )
    return {
        "id": timestamp.id,
        "type": timestamp.type,
        "created_at": localtime(timestamp.created_at),
        "notes": timestamp.notes,
    }


class SliceOut(Schema):
    starts_at: dt.datetime | None
    ends_at: dt.datetime | None
    hours: Decimal | None
    description: str
    comment: str
    project: ProjectSummary | None
    is_logged: bool
    log_hours_url: str | None


class TimestampList(Schema):
    day: dt.date
    url: str
    logged_hours: Decimal
    slices: list[SliceOut]


def _local(value):
    return localtime(value) if value else None


@router.get("/timestamps/", response=TimestampList)
def timestamp_list(request, day: dt.date | None = None):
    """The slices of a day (today by default) made of timestamps, logged hours
    and breaks, like on the timestamps page

    Hours aren't logged through the API on purpose, ``log_hours_url`` opens
    the form of the web interface."""
    day = day or localdate()
    slices = Timestamp.objects.slices(request.user, day=day)
    return {
        "day": day,
        "url": request.build_absolute_uri(f"{reverse('timestamps')}?day={day}"),
        "logged_hours": sum(
            (s["logged_hours"].hours for s in slices if s.get("logged_hours")), Z1
        ),
        "slices": [
            {
                "starts_at": _local(slice.get("starts_at")),
                "ends_at": _local(slice.get("ends_at")),
                "hours": slice.elapsed_hours,
                "description": str(slice["description"] or ""),
                "comment": slice.get("comment", ""),
                "project": project_summary(project, request)
                if (project := slice.get("project"))
                else None,
                "is_logged": slice.has_associated_log,
                "log_hours_url": request.build_absolute_uri(url)
                if (url := slice.hours_create_url)
                else None,
            }
            for slice in slices
        ],
    }
