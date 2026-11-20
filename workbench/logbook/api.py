import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.models import User
from workbench.api_keys import InvoiceStatus, key
from workbench.logbook.forms import LoggedHoursForm
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.api import ProjectSummary, project_summary
from workbench.projects.models import Service
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
    filter_date_range,
    form_data,
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


def _check_disabled(form, fields, message):
    """Fields which can't be changed anymore are errors, the form would
    silently keep their values"""
    if disabled := [f for f in fields if form.fields[f].disabled]:
        raise ValidationError([
            {"loc": ["body", "data", field], "msg": message} for field in disabled
        ])


def _save(form, request, out, *, dry_run):
    """Save the form, roll back with ``dry_run``; new entries have no ID
    and URL then"""
    is_new = not form.instance.pk
    with transaction.atomic():
        entry = form.save()
        result = out(entry, request)
        if dry_run:
            transaction.set_rollback(True)
            if is_new:
                result |= {"id": None, "url": None}
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
        description="ID of another service of the same project which allows logging.",
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
    Warnings are errors unless they are ignored by their code."""
    entry = get_object_or_404(
        LoggedHours.objects.select_related("service__project"), pk=hours_id
    )
    request = without_query(request)
    form = LoggedHoursForm(instance=entry, request=request, prefix=None)
    fields = data.model_dump(exclude_unset=True)
    _check_disabled(form, fields, _("These hours cannot be changed anymore."))
    form = LoggedHoursForm(
        _values(form_data(form), fields),
        instance=entry,
        request=request,
        prefix=None,
    )
    validate_form(form, ignore_warnings=ignore_warnings)
    return _save(form, request, _hours_out, dry_run=dry_run)


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
