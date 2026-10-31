import datetime as dt
import re
from decimal import Decimal
from typing import Literal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localdate, localtime, make_aware
from django.utils.translation import gettext as _
from ninja import Field, Router, Schema
from ninja.errors import HttpError, ValidationError

from workbench.logbook.models import LoggedHours
from workbench.projects.api import ProjectSummary, project_summary
from workbench.projects.models import Service
from workbench.reporting.utils import sum_of
from workbench.timer.models import Slice, Timestamp, timestamp_project
from workbench.tools.formats import Z1
from workbench.tools.validation import monday


router = Router(tags=["timer"])


def _codes(user, day):
    """Short codes of the day's timestamps: T1, T2, ... in chronological order

    Deleting a timestamp renumbers the following ones."""
    timestamps = Timestamp.objects.filter(user=user, created_at__date=day).order_by(
        "created_at", "pk"
    )
    return {
        pk: f"T{index}"
        for index, pk in enumerate(timestamps.values_list("pk", flat=True), 1)
    }


class SliceOut(Schema):
    timestamp_id: int | None
    timestamp_code: str | None
    starts_at: dt.datetime | None
    ends_at: dt.datetime | None
    hours: Decimal | None
    description: str
    comment: str
    project: ProjectSummary | None
    is_logged: bool
    log_hours_url: str | None


def _local(value):
    return localtime(value) if value else None


def _slice_out(slice, request, *, codes):
    return {
        "timestamp_id": slice.get("timestamp_id"),
        "timestamp_code": codes.get(slice.get("timestamp_id")),
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
    project: int | str | None = Field(
        default=None,
        description="Pre-fills the logbook form of the slice. An ID or a part of"
        " the code, title or customer of one of your pinned projects.",
    )
    service: int | None = Field(
        default=None,
        description="Pre-fills the logbook form of the slice, the project"
        " defaults to the service's.",
    )


class TimestampOut(Schema):
    id: int
    code: str
    type: str
    created_at: dt.datetime
    notes: str
    project: ProjectSummary | None
    service_id: int | None
    slice: SliceOut | None


def _timestamp_out(timestamp, request, *, with_slice=True):
    codes = _codes(timestamp.user, localdate(timestamp.created_at))
    slice = timestamp.slice() if with_slice else None
    return {
        "id": timestamp.id,
        "code": codes[timestamp.id],
        "type": timestamp.type,
        "created_at": localtime(timestamp.created_at),
        "notes": timestamp.notes,
        "project": project_summary(timestamp.project, request)
        if timestamp.project
        else None,
        "service_id": timestamp.service_id,
        "slice": _slice_out(slice, request, codes=codes) if slice else None,
    }


def _error(field, msg):
    return ValidationError([{"loc": ["body", "data", field], "msg": msg}])


def _project(user, value):
    try:
        return timestamp_project(user, value)
    except DjangoValidationError as exc:
        raise _error("project", exc.messages[0]) from exc


def _project_and_service(user, data):
    project = _project(user, data.project) if data.project is not None else None
    service = None
    if data.service is not None:
        service = Service.objects.select_related("project").filter(pk=data.service)
        if not (service := service.first()):
            raise _error("service", _("This service doesn't exist."))
        if project and project != service.project:
            raise _error("service", _("This service belongs to a different project."))
        project = service.project
    return project, service


@router.post("/timestamps/", response=TimestampOut)
def timestamp_create(request, data: TimestampIn):
    """Start or stop a task, like the timer in the web interface

    ``slice`` is the slice the timestamp belongs to, e.g. the task which has
    been stopped."""
    if data.time is not None and data.minutes is not None:
        raise ValidationError([
            {"loc": ["body", "data"], "msg": _("Pass either time or minutes.")}
        ])
    project, service = _project_and_service(request.user, data)
    created_at = timezone.now()
    if data.time is not None:
        created_at = make_aware(dt.datetime.combine(localdate(), data.time))
    elif data.minutes is not None:
        created_at += dt.timedelta(minutes=data.minutes)
    timestamp = Timestamp.objects.create(
        user=request.user,
        type=data.type,
        notes=data.notes,
        created_at=created_at,
        project=project,
        service=service,
    )
    return _timestamp_out(timestamp, request)


@router.delete("/timestamps/latest/", response=TimestampOut)
def timestamp_delete_latest(request):
    """Delete the latest timestamp of today, e.g. to undo a typo"""
    timestamp = (
        Timestamp.objects
        .filter(user=request.user, created_at__date=localdate())
        .order_by("-created_at", "-pk")
        .first()
    )
    if not timestamp:
        raise HttpError(404, _("There are no timestamps today."))
    result = _timestamp_out(timestamp, request, with_slice=False)
    timestamp.delete()
    return result


@router.delete("/timestamps/{timestamp}/", response=TimestampOut)
def timestamp_delete(request, timestamp: str, day: dt.date | None = None):
    """Delete a timestamp by its code (T1, T2, ... of the day, today by
    default) or its ID, both are in the list of slices"""
    timestamps = Timestamp.objects.filter(user=request.user)
    if match := re.fullmatch(r"[tT]([0-9]+)", timestamp):
        codes = {
            code: pk for pk, code in _codes(request.user, day or localdate()).items()
        }
        timestamp = get_object_or_404(timestamps, pk=codes.get(f"T{int(match[1])}", 0))
    elif re.fullmatch(r"[0-9]+", timestamp):
        timestamp = get_object_or_404(timestamps, pk=timestamp)
    else:
        raise HttpError(404, _("Use a code like T1 or an ID."))
    result = _timestamp_out(timestamp, request, with_slice=False)
    timestamp.delete()
    return result


class TimestampList(Schema):
    day: dt.date
    url: str
    logged_hours: Decimal
    weekly_hours: Decimal
    running_since: dt.datetime | None
    running_hours: Decimal | None
    slices: list[SliceOut]


@router.get("/timestamps/", response=TimestampList)
def timestamp_list(request, day: dt.date | None = None):
    """The slices of a day (today by default) made of timestamps, logged hours
    and breaks, like on the timestamps page

    Hours aren't logged through the API on purpose, ``log_hours_url`` opens
    the form of the web interface. ``running_since`` is the end of the last
    slice (or the start of a task which hasn't been stopped yet) if the day
    is today, ``weekly_hours`` the hours logged in the day's week."""
    now = timezone.now()
    day = day or localdate(now)
    slices = Timestamp.objects.slices(request.user, day=day)
    codes = _codes(request.user, day)
    running_since = None
    if day == localdate(now) and slices:
        running_since = slices[-1].get("ends_at") or slices[-1].get("starts_at")
        if running_since > now:
            running_since = None
    return {
        "day": day,
        "url": request.build_absolute_uri(f"{reverse('timestamps')}?day={day}"),
        "logged_hours": sum(
            (s["logged_hours"].hours for s in slices if s.get("logged_hours")), Z1
        ),
        "weekly_hours": sum_of(
            LoggedHours.objects.filter(
                rendered_by=request.user,
                rendered_on__gte=monday(day),
                rendered_on__lt=monday(day) + dt.timedelta(days=7),
            ),
            field="hours",
            default=Z1,
        ),
        "running_since": _local(running_since),
        "running_hours": Slice(
            description="", starts_at=running_since, ends_at=now
        ).elapsed_hours
        if running_since
        else None,
        "slices": [_slice_out(slice, request, codes=codes) for slice in slices],
    }
