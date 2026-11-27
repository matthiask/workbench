import datetime as dt
import html
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import check_feature
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.api_keys import AbsenceReason
from workbench.awt.forms import AbsenceForm
from workbench.awt.models import Absence
from workbench.awt.reporting import (
    active_users,
    annual_working_time,
    working_time_by_week,
)
from workbench.tools.api import (
    DATES,
    IGNORE_WARNINGS,
    DateRangeFilter,
    Days,
    DryRun,
    Hours,
    InputSchema,
    Percentage,
    Serialized,
    ShortName,
    active_user,
    check_allow_delete,
    date_range,
    delete_with_form,
    patch_with_form,
    user_by_short_name,
    validate_form,
    without_query,
)


router = Router(tags=["absences"])


class AbsenceOut(Schema):
    id: int | None
    url: str | None
    user: str
    starts_on: dt.date
    ends_on: dt.date | None
    days: Days
    reason: AbsenceReason
    reason_label: str
    description: str
    is_confirmed: bool = Field(
        description="False for paid leave not checked yet, it counts anyway."
    )


class AbsenceFilter(DateRangeFilter):
    user: ShortName = None
    reason: AbsenceReason | None = Field(
        default=None, description="Absence reason, see /api/choices/."
    )


@router.get("/absences/", response=list[AbsenceOut])
@paginate
def absence_list(request, filters: Query[AbsenceFilter]):
    """Absences overlapping the period (or from ``since`` until ``until``), oldest
    first"""
    absences = Absence.objects.select_related("user")
    if filters.user:
        absences = absences.filter(user=user_by_short_name(filters.user, param="user"))
    if filters.reason:
        absences = absences.filter(reason=filters.reason)
    since, until = date_range(filters)
    if since:
        absences = absences.filter(
            Q(ends_on__gte=since) | Q(ends_on__isnull=True, starts_on__gte=since)
        )
    if until:
        absences = absences.filter(starts_on__lte=until)
    return Serialized(
        absences.order_by("starts_on", "pk"),
        lambda absence: _absence_out(absence, request),
    )


def _absence_out(absence, request):
    return {
        "id": absence.id,
        "url": request.build_absolute_uri(absence.get_absolute_url()),
        "user": absence.user.get_short_name(),
        "starts_on": absence.starts_on,
        "ends_on": absence.ends_on,
        "days": absence.days,
        "reason": absence.reason,
        "reason_label": absence.get_reason_display(),
        "description": absence.description_for(request.user),
        "is_confirmed": not absence.needs_confirmation,
    }


class AbsenceIn(InputSchema):
    user: str | None = Field(
        default=None, description="Short name, defaults to the authenticated user."
    )
    starts_on: dt.date
    ends_on: dt.date | None = Field(
        default=None, description="In the same year, empty for a single day."
    )
    days: Decimal = Field(gt=0, description="Working days, e.g. 0.5.")
    reason: AbsenceReason
    description: str = ""


@router.post("/absences/", response=AbsenceOut)
def absence_create(
    request,
    data: AbsenceIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create an absence, validated like in the web interface

    Warnings of the web interface are errors here unless they are ignored;
    nothing is saved if anything is invalid or with ``dry_run``."""
    user = request.user
    if data.user is not None:
        user = User.objects.by_short_name(data.user).first()
        if not user:
            raise ValidationError([
                {"loc": ["body", "data", "user"], "msg": _("Unknown user.")}
            ])
    form = AbsenceForm(
        {
            "user": user.pk,
            "starts_on": data.starts_on,
            "ends_on": data.ends_on or "",
            "days": data.days,
            "reason": data.reason,
            "description": data.description,
        },
        request=request,
        # The web interface shows the form in a modal
        prefix=None,
    )
    validate_form(form, ignore_warnings=ignore_warnings)
    with transaction.atomic():
        absence = form.save()
        result = _absence_out(absence, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
    return result


class AbsencePatch(InputSchema):
    user: str | None = Field(
        default=None,
        description="Short name of an active user; only personnel administration"
        " hands absences over to others.",
    )
    starts_on: dt.date | None = None
    ends_on: dt.date | None = Field(
        default=None, description="In the same year, null for a single day."
    )
    days: Decimal | None = Field(
        default=None, description="Working days, only corrections are negative."
    )
    reason: AbsenceReason | None = None
    description: str | None = None


def _absence(request, absence_id):
    """The absence if the user may change or delete it like in the web
    interface (``Absence.allow_update``, which is ``allow_delete`` too)"""
    absence = get_object_or_404(Absence.objects.select_related("user"), pk=absence_id)
    check_allow_delete(absence, request, ["path", "absence_id"])
    return absence


@router.patch("/absences/{int:absence_id}/", response=AbsenceOut)
def absence_update(
    request,
    absence_id: int,
    data: AbsencePatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change an absence, validated like in the web interface

    Only the absent person and personnel administration change absences
    (whoever entered one for someone else may undo it on the same day),
    absences of past years are locked. Descriptions of sickness stay hidden
    from others, also here. A sickness absence with a description keeps its
    reason: clear the description, or create a new absence and delete this
    one. Warnings of the web interface are errors here unless they are
    ignored by their code; nothing is saved if anything is invalid or with
    ``dry_run``."""
    absence = _absence(request, absence_id)
    try:
        return patch_with_form(
            # The web interface shows the form in a modal
            AbsenceForm.__wrapped__,
            absence,
            data,
            # The form takes initial values from the query string
            without_query(request),
            out=lambda absence: _absence_out(absence, request),
            ignore_warnings=ignore_warnings,
            dry_run=dry_run,
            field_map={"user": active_user},
        )
    except ValidationError as exc:
        # The form links to replacing the absence in the web interface
        for error in exc.errors:
            error["msg"] = html.unescape(strip_tags(str(error["msg"])))
        raise


@router.delete("/absences/{int:absence_id}/", response=AbsenceOut)
def absence_delete(request, absence_id: int, *, dry_run: DryRun = False):
    """Delete an absence like in the web interface: allowed for the same
    people as changing it

    Deleting the absence of someone else is listed in the weekly mail to
    personnel administration, like all their changes. Returns the deleted
    absence."""
    absence = _absence(request, absence_id)
    result = _absence_out(absence, request)
    delete_with_form(absence, request, loc=["path", "absence_id"], dry_run=dry_run)
    return result


class WorkingTimeFilter(Schema):
    year: int | None = Field(
        default=None,
        ge=DATES[0].year,
        le=DATES[1].year,
        description="This year by default.",
    )
    user: ShortName = None
    all: bool = Field(
        default=False,
        description="All active users (requires personnel administration for others).",
    )
    weekly: bool = Field(default=False, description="Add the working time per week.")


MONTHLY_DAYS = {
    "vacation_days": "absence_vacation",
    "sickness_days": "absence_sickness",
    "paid_days": "absence_paid",
    "school_days": "absence_school",
    "correction_days": "absence_correction",
    "public_holiday_days": "holiday_public",
    "company_holiday_days": "holiday_company",
}


class WorkingTimeMonth(Schema):
    month: str
    percentage: Percentage
    target: Hours
    hours: Hours
    absences_time: Hours
    working_time: Hours
    balance: Hours
    running_balance: Hours
    vacation_days: Days
    sickness_days: Days
    paid_days: Days
    school_days: Days
    correction_days: Days
    public_holiday_days: Days
    company_holiday_days: Days


class WorkingTimeTotals(Schema):
    percentage: Percentage
    target: Hours
    hours: Hours
    absences_time: Hours
    working_time: Hours
    running_sum: Hours
    available_vacation_days: Days
    absence_vacation: Days
    vacation_days_correction: Days
    vacation_days_credit: Days
    balance: Hours
    balance_days: Days
    absence_sickness: Days
    absence_paid: Days
    absence_school: Days
    absence_correction: Days
    holiday_public: Days
    holiday_company: Days
    balance_as_of: Hours | None
    vacation_days_taken: Days
    vacation_days_planned: Days
    vacation_days_left: Days
    absences_planned: Days


class WorkingTimeWeek(Schema):
    week: dt.date
    target: Hours
    hours: Hours
    absences: Hours
    delta: Hours
    running_delta: Hours


class UserWorkingTime(Schema):
    user: str
    working_time_per_day: Hours
    as_of: dt.date | None
    months: list[WorkingTimeMonth]
    totals: WorkingTimeTotals
    weeks: list[WorkingTimeWeek] | None


class WorkingTimeSummary(Schema):
    user: str
    is_active: bool
    percentage: Percentage
    as_of: dt.date | None
    balance_as_of: Hours | None
    vacation_days_left: Days
    vacation_days_planned: Days
    vacation_planning_fine: bool
    absences_planned: Days = Field(
        description="Future absences except vacation, e.g. sickness or unpaid leave."
    )


class WorkingTime(Schema):
    year: int
    warnings: list[str]
    users: list[UserWorkingTime]
    summary: list[WorkingTimeSummary] | None


@router.get("/reports/working-time/", response=WorkingTime)
def working_time(request, filters: Query[WorkingTimeFilter]):
    """Annual working time of the authenticated user, of the user with the
    given short name, or of ``all`` users employed during the year. Everyone
    gets the ``summary`` of ``all`` (balance, vacation and planned absences,
    for planning), the details of others (``users``) require the personnel
    administration feature like in the web interface.

    Hours are per month: The target, logged hours, absences and their sum
    (working time) and the balance. ``balance_as_of`` is the running balance
    at the end of the last completed month (``as_of``), the vacation days are
    split into taken (until today), planned and left. The total ``balance``
    includes the vacation days credit. ``weekly`` adds the hours per week
    until the current one."""
    year = filters.year or dt.date.today().year
    details = request.user.features[FEATURES.PERSONNEL_ADMINISTRATION]
    if filters.all:
        users = list(active_users(year))
    elif (
        filters.user and filters.user.casefold() != request.user._short_name.casefold()
    ):
        if not details:
            check_feature(request.user, FEATURES.PERSONNEL_ADMINISTRATION)
        users = list(User.objects.by_short_name(filters.user))
        if not users:
            raise ValidationError([
                {"loc": ["query", "filters", "user"], "msg": _("Unknown user.")}
            ])
    else:
        users = [request.user]

    statistics = annual_working_time(year, users=users)
    warnings = [
        _(
            "The annual working time %(year)s of the working time model"
            " %(working_time_model)s is not configured correctly:"
            " The working time per day is zero."
        )
        % {"year": y.year, "working_time_model": y.working_time_model}
        for y in statistics["months"].misconfigured_years
    ] + [
        _(
            "No annual working time defined for user %(user)s"
            " with working time model %(working_time_model)s."
        )
        % {"user": user, "working_time_model": user.working_time_model}
        for user in statistics["months"].users_without_wtm
    ]

    def _user(row):
        months = row["months"]
        return {
            "user": row["user"].get_short_name(),
            "working_time_per_day": months["year"].working_time_per_day,
            "as_of": row["as_of"],
            "months": [
                {
                    "month": f"{month:%Y-%m}",
                    "percentage": months["percentage"][i],
                    "target": months["target"][i],
                    "hours": months["hours"][i],
                    "absences_time": row["absences_time"][i],
                    "working_time": row["working_time"][i],
                    "balance": row["monthly_sums"][i],
                    "running_balance": row["running_sums"][i],
                }
                | {key: months[field][i] for key, field in MONTHLY_DAYS.items()}
                for i, month in enumerate(months["months"])
            ],
            "totals": row["totals"],
            "weeks": working_time_by_week(year, user=row["user"])
            if filters.weekly
            else None,
        }

    def _summary(row):
        totals = row["totals"]
        return {
            "user": row["user"].get_short_name(),
            "is_active": row["user"].is_active,
            "percentage": totals["percentage"],
            "as_of": row["as_of"],
            "balance_as_of": totals["balance_as_of"],
            "vacation_days_left": totals["vacation_days_left"],
            "vacation_days_planned": totals["vacation_days_planned"],
            "vacation_planning_fine": row["vacation_planning"]["fine"],
            "absences_planned": totals["absences_planned"],
        }

    rows = statistics["statistics"]
    return {
        "year": year,
        "warnings": [str(warning) for warning in warnings],
        "users": [_user(row) for row in rows] if details or not filters.all else [],
        "summary": [_summary(row) for row in rows] if filters.all else None,
    }
