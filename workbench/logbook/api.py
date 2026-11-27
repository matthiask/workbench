import datetime as dt
from decimal import Decimal
from typing import Any, Literal

from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from django.utils.timezone import localtime
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.models import User
from workbench.api_keys import InvoiceStatus, key
from workbench.logbook.forms import (
    BreakForm,
    LogbookBatchForm,
    LoggedCostForm,
    LoggedCostMoveForm,
    LoggedHoursForm,
    LoggedHoursMoveForm,
)
from workbench.logbook.models import Break, LoggedCost, LoggedHours
from workbench.projects.api import ProjectSummary, project_summary
from workbench.projects.models import Project, Service
from workbench.tools.api import (
    IGNORE_WARNINGS,
    DateRangeFilter,
    DryRun,
    InputSchema,
    Number,
    OrganizationID,
    ProjectID,
    SearchQuery,
    Serialized,
    ShortName,
    TotalsPagination,
    check_allow_delete,
    delete_with_form,
    filter_date_range,
    form_data,
    patch_with_form,
    user_by_short_name,
    validate_form,
    without_query,
)
from workbench.tools.formats import Z1, Z2


# Changes are validated with the forms of the web interface, their warnings
# are errors unless they're ignored by their code
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
    created_at: dt.datetime = Field(description="When the entry was logged.")
    hours: Decimal
    hours_for_invoicing: Decimal | None = Field(
        description="If set, the work is valued and invoiced with these hours"
        " instead of the hours, e.g. if it's worth more than the time spent."
    )
    description: str
    project: ProjectSummary
    service_id: int
    service: str
    offer_id: int | None = Field(description="The offer of the service, if any.")
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
    offer: int | None = Field(default=None, description="ID of the offer.")
    service: int | None = Field(default=None, description="ID of the service.")
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
        "created_at": entry.created_at,
        "description": entry.description,
        "project": project_summary(entry.service.project, request),
        "service_id": entry.service_id,
        "service": entry.service.title,
        "offer_id": entry.service.offer_id,
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
            "rendered_by",
            "service__project__customer",
            "invoice_service__invoice__project",
        ).order_by("-rendered_on", "-created_at", "-pk"),
        lambda row: _hours_out(row, request),
        totals={
            "total_hours": hours.order_by().aggregate(Sum("hours"))["hours__sum"] or Z1
        },
    )


class LoggedCostOut(Schema):
    id: int
    url: str
    rendered_on: dt.date
    rendered_by: str
    created_at: dt.datetime = Field(description="When the entry was logged.")
    cost: Decimal
    third_party_costs: Decimal | None
    are_expenses: bool
    description: str
    project: ProjectSummary
    service_id: int
    service: str
    offer_id: int | None = Field(description="The offer of the service, if any.")
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
    expenses: bool = Field(default=False, description="Only costs which are expenses.")


def _cost_out(entry, request):
    return _entry_out(entry, request) | {
        "cost": entry.cost,
        "third_party_costs": entry.third_party_costs,
        "are_expenses": entry.are_expenses,
    }


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
            "rendered_by",
            "service__project__customer",
            "invoice_service__invoice__project",
        ).order_by("-rendered_on", "-created_at", "-pk"),
        lambda row: _cost_out(row, request),
        totals={
            "total_cost": totals["cost"] or Z2,
            "total_third_party_costs": totals["third_party_costs"] or Z2,
        },
    )


def _hours_out(entry, request):
    return _entry_out(entry, request) | {
        "hours": entry.hours,
        "hours_for_invoicing": entry.hours_for_invoicing,
    }


def _rendered_by(short_name):
    if user := User.objects.by_short_name(short_name).first():
        return user.pk
    raise ValidationError([
        {
            "loc": ["body", "data", "rendered_by"],
            "msg": _("Unknown user %r.") % short_name,
        }
    ])


def _values(values, fields):
    """Apply the fields of the API to the data of a logbook form"""
    for field, value in fields.items():
        if field == "rendered_by":
            values[field] = _rendered_by(value)
        elif field == "description":
            values[field] = value.strip()
        else:
            values[field] = "" if value is None else value
    return values


def _check_fields(form, fields, message):
    """Fields which can't be changed anymore are errors, the form would
    silently keep their values; so are fields of features the user doesn't
    have"""
    errors = [
        {"loc": ["body", "data", field], "msg": message}
        for field in fields
        if field in form.fields and form.fields[field].disabled
    ] + [
        {
            "loc": ["body", "data", field],
            "msg": _("This field isn't available to you."),
        }
        for field in fields
        if field != "service" and field not in form.fields
    ]
    if errors:
        raise ValidationError(errors)


def _save(form, request, out, *, dry_run):
    """Save the form, roll back with ``dry_run``; new entries have no ID
    and URL then"""
    is_new = not form.instance.pk
    with transaction.atomic():
        entry = form.save()
        # Values as stored, e.g. amounts with two decimal places
        entry.refresh_from_db()
        result = out(entry, request)
        if dry_run:
            transaction.set_rollback(True)
            if is_new:
                result |= {"id": None, "url": None}
    return result


def _update(
    entry,
    fields,
    request,
    *,
    form_class,
    move_form_class,
    out,
    message,
    ignore_warnings,
    dry_run,
):
    """Change the entry with the form of the web interface, which only
    offers services of the same project; a service of another project moves
    the entry with the move form first, like the web interface does in a
    separate step. Errors of the other fields roll back the move too."""
    request = without_query(request)
    with transaction.atomic():
        if (service := fields.get("service")) is not None and Service.objects.filter(
            pk=service
        ).exclude(project=entry.service.project_id).exists():
            form = move_form_class(
                {"service": service}, instance=entry, request=request, prefix=None
            )
            validate_form(form)
            form.save()
            entry = (
                type(entry).objects.select_related("service__project").get(pk=entry.pk)
            )
            fields = {key: value for key, value in fields.items() if key != "service"}
            if not fields:
                result = out(entry, request)
                if dry_run:
                    transaction.set_rollback(True)
                return result

        form = form_class(instance=entry, request=request, prefix=None)
        _check_fields(form, fields, message)
        form = form_class(
            _values(form_data(form), fields),
            instance=entry,
            request=request,
            prefix=None,
        )
        validate_form(form, ignore_warnings=ignore_warnings)
        result = _save(form, request, out, dry_run=False)
        if dry_run:
            transaction.set_rollback(True)
    return result


class LoggedHoursResult(LoggedHoursOut):
    id: int | None = Field(description="Null with dry_run.")
    url: str | None = Field(description="Null with dry_run.")


class LoggedHoursFields(InputSchema):
    rendered_on: dt.date | None = Field(default=None, description="Defaults to today.")
    rendered_by: str | None = Field(
        default=None, description="Short name of a user, defaults to you."
    )
    hours: Number | None = Field(default=None, gt=0)
    hours_for_invoicing: Number | None = Field(
        default=None,
        ge=0,
        description="If set, the work is valued and invoiced with these hours"
        " instead of the hours; null removes them.",
    )
    description: str | None = Field(default=None, min_length=1)


class LoggedHoursCreate(LoggedHoursFields):
    service: int = Field(description="ID of a service which allows logging.")
    hours: Number = Field(gt=0)
    description: str = Field(min_length=1)


class LoggedHoursPatch(LoggedHoursFields):
    """Fields which aren't given are left alone"""

    service: int | None = Field(
        default=None,
        description="ID of another service which allows logging; services of"
        " other open projects move the entry there.",
    )


@router.post("/logbook/hours/", response=LoggedHoursResult)
def logged_hours_create(
    request,
    data: LoggedHoursCreate,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Log hours, validated like in the web interface

    Warnings of the web interface (e.g. ``maybe-duplicate`` or
    ``take-a-break``) are errors unless they are ignored by their code.
    The ID and the URL are null with ``dry_run``."""
    service = get_object_or_404(
        Service.objects.select_related("project"), pk=data.service
    )
    request = without_query(request)
    values = _values(
        {
            "rendered_by": request.user.pk,
            "rendered_on": dt.date.today(),
            "hours_for_invoicing": "",
        },
        data.model_dump(exclude_unset=True),
    )
    form = LoggedHoursForm(
        values, project=service.project, request=request, prefix=None
    )
    validate_form(form, ignore_warnings=ignore_warnings)
    return _save(form, request, _hours_out, dry_run=dry_run)


@router.patch("/logbook/hours/{int:hours_id}/", response=LoggedHoursOut)
def logged_hours_update(
    request,
    hours_id: int,
    data: LoggedHoursPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change logged hours, validated like in the web interface

    Hours of past weeks keep their date, person and hours (except for people
    who may log late), invoiced hours only allow changing the description.
    A service of another open project moves the hours there, not when they
    have been invoiced or their project has been closed. Warnings are errors
    unless they are ignored by their code."""
    entry = get_object_or_404(
        LoggedHours.objects.select_related("service__project"), pk=hours_id
    )
    return _update(
        entry,
        data.model_dump(exclude_unset=True),
        request,
        form_class=LoggedHoursForm,
        move_form_class=LoggedHoursMoveForm,
        out=_hours_out,
        message=_("These hours cannot be changed anymore."),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
    )


@router.delete("/logbook/hours/{int:hours_id}/", response=LoggedHoursOut)
def logged_hours_delete(request, hours_id: int, *, dry_run: DryRun = False):
    """Delete logged hours like in the web interface: not when they have
    been invoiced or are from past weeks (except for people who may log
    late)

    Returns the deleted entry."""
    entry = get_object_or_404(
        LoggedHours.objects.select_related("service__project"), pk=hours_id
    )
    check_allow_delete(entry, request, ["path", "hours_id"])
    result = _hours_out(entry, request)
    if not dry_run:
        entry.delete()
    return result


class LoggedCostResult(LoggedCostOut):
    id: int | None = Field(description="Null with dry_run.")
    url: str | None = Field(description="Null with dry_run.")


class LoggedCostFields(InputSchema):
    rendered_on: dt.date | None = Field(default=None, description="Defaults to today.")
    rendered_by: str | None = Field(
        default=None, description="Short name of a user, defaults to you."
    )
    cost: Number | None = Field(default=None, description="Excl. tax.")
    third_party_costs: Number | None = Field(
        default=None,
        description="Total incl. tax for third parties contained in the cost;"
        " null removes them.",
    )
    are_expenses: bool | None = Field(
        default=None,
        description="Paid from your own pocket, needs third party costs.",
    )
    expense_currency: str | None = Field(
        default=None,
        description="Currency of expenses in foreign currencies, together with"
        " expense_cost.",
    )
    expense_cost: Number | None = Field(
        default=None, description="Expenses in the foreign currency."
    )
    description: str | None = Field(default=None, min_length=1)


class LoggedCostCreate(LoggedCostFields):
    service: int = Field(description="ID of a service which allows logging.")
    cost: Number = Field(description="Excl. tax.")
    description: str = Field(min_length=1)


class LoggedCostPatch(LoggedCostFields):
    """Fields which aren't given are left alone"""

    service: int | None = Field(
        default=None,
        description="ID of another service which allows logging; services of"
        " other open projects move the entry there.",
    )


@router.post("/logbook/costs/", response=LoggedCostResult)
def logged_cost_create(
    request,
    data: LoggedCostCreate,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Log costs, validated like in the web interface

    Warnings of the web interface (e.g. ``third-party-costs-higher``) are
    errors unless they are ignored by their code. The ID and the URL are
    null with ``dry_run``."""
    service = get_object_or_404(
        Service.objects.select_related("project"), pk=data.service
    )
    request = without_query(request)
    fields = data.model_dump(exclude_unset=True)
    form = LoggedCostForm(project=service.project, request=request, prefix=None)
    _check_fields(form, fields, _("These costs cannot be changed anymore."))
    values = _values(
        {
            "rendered_by": request.user.pk,
            "rendered_on": dt.date.today(),
            "third_party_costs": "",
            "are_expenses": False,
            "expense_currency": "",
            "expense_cost": "",
        },
        fields,
    )
    form = LoggedCostForm(values, project=service.project, request=request, prefix=None)
    validate_form(form, ignore_warnings=ignore_warnings)
    return _save(form, request, _cost_out, dry_run=dry_run)


@router.patch("/logbook/costs/{int:cost_id}/", response=LoggedCostOut)
def logged_cost_update(
    request,
    cost_id: int,
    data: LoggedCostPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change logged costs, validated like in the web interface

    Invoiced costs keep their service, date, person and amounts, costs of
    expense reports their date, person and expenses. A service of another
    open project moves the costs there, not when they have been invoiced or
    their project has been closed. Warnings are errors unless they are
    ignored by their code."""
    entry = get_object_or_404(
        LoggedCost.objects.select_related("service__project"), pk=cost_id
    )
    return _update(
        entry,
        data.model_dump(exclude_unset=True),
        request,
        form_class=LoggedCostForm,
        move_form_class=LoggedCostMoveForm,
        out=_cost_out,
        message=_("These costs cannot be changed anymore."),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
    )


@router.delete("/logbook/costs/{int:cost_id}/", response=LoggedCostOut)
def logged_cost_delete(request, cost_id: int, *, dry_run: DryRun = False):
    """Delete logged costs like in the web interface: not when they have
    been invoiced or are part of an expense report

    Returns the deleted entry."""
    entry = get_object_or_404(
        LoggedCost.objects.select_related("service__project"), pk=cost_id
    )
    check_allow_delete(entry, request, ["path", "cost_id"])
    result = _cost_out(entry, request)
    if not dry_run:
        entry.delete()
    return result


class LogbookMove(InputSchema):
    kind: Literal["hours", "costs"]
    entries: list[int] = Field(
        min_length=1,
        description="IDs of hours or costs of the project which haven't been invoiced.",
    )
    service: int = Field(
        description="ID of a service of the same project which allows logging."
    )


@router.post(
    "/projects/{project_id}/logbook/move/",
    response=list[LoggedHoursOut] | list[LoggedCostOut],
)
def logbook_move(
    request,
    project_id: int,
    data: LogbookMove,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Move hours or costs of a project to another service of the same
    project at once, like the logbook batch update of the web interface

    Not for invoiced entries or closed projects; ``PATCH`` moves single
    entries to other projects. Nothing is saved if anything is invalid or
    with ``dry_run``. Returns the moved entries."""
    project = get_object_or_404(Project, pk=project_id)
    if project.closed_on:
        raise ValidationError([
            {
                "loc": ["path", "project_id"],
                "msg": _("Cannot move logbook entries of closed projects."),
            }
        ])
    model, out = (
        (LoggedHours, _hours_out) if data.kind == "hours" else (LoggedCost, _cost_out)
    )
    form = LogbookBatchForm(
        {"entries": data.entries, "service": data.service},
        request=request,
        project=project,
        entries=model.objects.filter(service__project=project).select_related(
            "rendered_by", "service"
        ),
    )
    validate_form(form, ignore_warnings=ignore_warnings)
    with transaction.atomic():
        form.process()
        result = [
            out(entry, request)
            for entry in model.objects
            .filter(pk__in=data.entries)
            .select_related(
                "rendered_by",
                "service__project__customer",
                "invoice_service__invoice__project",
            )
            .order_by("-rendered_on", "-created_at", "-pk")
        ]
        if dry_run:
            transaction.set_rollback(True)
    return result


# Breaks ######################################################################
#
# Breaks count for the working time. Everyone sees everyone's breaks like in
# the web interface, but only changes and deletes their own
# (``Break.allow_update``, which is also ``Break.allow_delete``).


class BreakOut(Schema):
    id: int
    url: str
    user: str = Field(description="Short name of the user taking the break.")
    day: dt.date
    starts_at: dt.datetime
    ends_at: dt.datetime
    minutes: int
    description: str


class BreakResult(BreakOut):
    id: int | None = Field(description="Null with dry_run.")
    url: str | None = Field(description="Null with dry_run.")


class BreakPagination(TotalsPagination):
    class Output(Schema):
        items: list[Any]
        count: int
        total_minutes: int


class BreakFilter(DateRangeFilter):
    q: str = Field(default="", description="Search the description.")
    user: ShortName = None


def _minutes(timedelta):
    return round(timedelta.total_seconds() / 60) if timedelta else 0


def _break_out(brk, request, *, dry_run=False):
    starts_at = localtime(brk.starts_at)
    return {
        "id": None if dry_run else brk.id,
        "url": None if dry_run else request.build_absolute_uri(brk.get_absolute_url()),
        "user": brk.user.get_short_name(),
        "day": starts_at.date(),
        "starts_at": starts_at,
        "ends_at": localtime(brk.ends_at),
        "minutes": _minutes(brk.timedelta),
        "description": brk.description,
    }


@router.get("/logbook/breaks/", response=list[BreakOut])
@paginate(BreakPagination)
def break_list(request, filters: Query[BreakFilter]):
    """Breaks of everyone (``user`` filters), newest first; the total
    includes all matching breaks

    The period filters the day of the break."""
    breaks = Break.objects.all()
    if filters.user:
        breaks = breaks.filter(user=user_by_short_name(filters.user, param="user"))
    if filters.q:
        breaks = breaks.filter(description__icontains=filters.q)
    breaks = filter_date_range(breaks, filters, "starts_at__date")
    total = breaks.order_by().aggregate(total=Sum(F("ends_at") - F("starts_at")))
    return Serialized(
        breaks.select_related("user").order_by("-starts_at", "-pk"),
        lambda row: _break_out(row, request),
        totals={"total_minutes": _minutes(total["total"])},
    )


class BreakFields(InputSchema):
    day: dt.date | None = Field(default=None, description="Defaults to today.")
    starts_at: dt.time | None = Field(default=None, description="Time of the day.")
    ends_at: dt.time | None = Field(
        default=None, description="Time of the day, the same day as the start."
    )
    description: str | None = None


class BreakCreate(BreakFields):
    starts_at: dt.time = Field(description="Time of the day.")
    ends_at: dt.time = Field(description="Time of the day.")


class BreakPatch(BreakFields):
    """Fields which aren't given are left alone; the times stay on the day
    of the break unless ``day`` is given too"""


@router.post("/logbook/breaks/", response=BreakResult)
def break_create(
    request,
    data: BreakCreate,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Log a break of your own, validated like in the web interface

    The ID and the URL are null with ``dry_run``."""
    request = without_query(request)
    values = {"day": dt.date.today(), "description": ""} | {
        field: "" if value is None else value
        for field, value in data.model_dump(exclude_unset=True).items()
    }
    form = BreakForm.__wrapped__(values, request=request)
    validate_form(form, ignore_warnings=ignore_warnings)
    with transaction.atomic():
        result = _break_out(form.save(), request, dry_run=dry_run)
        if dry_run:
            transaction.set_rollback(True)
    return result


def _own_break(request, break_id):
    brk = get_object_or_404(Break.objects.select_related("user"), pk=break_id)
    # Break.allow_delete is Break.allow_update: only own breaks
    check_allow_delete(brk, request, ["path", "break_id"])
    return brk


@router.patch("/logbook/breaks/{int:break_id}/", response=BreakOut)
def break_update(
    request,
    break_id: int,
    data: BreakPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change a break of your own, validated like in the web interface"""
    brk = _own_break(request, break_id)
    request = without_query(request)
    return patch_with_form(
        BreakForm.__wrapped__,
        brk,
        data,
        request,
        out=lambda brk: _break_out(brk, request),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
    )


@router.delete("/logbook/breaks/{int:break_id}/", response=BreakOut)
def break_delete(request, break_id: int, *, dry_run: DryRun = False):
    """Delete a break of your own like in the web interface

    Returns the deleted break."""
    brk = _own_break(request, break_id)
    result = _break_out(brk, request)
    delete_with_form(brk, request, loc=["path", "break_id"], dry_run=dry_run)
    return result
