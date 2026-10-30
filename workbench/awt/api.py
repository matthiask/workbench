import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import check_feature
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.forms import AbsenceForm
from workbench.awt.models import Absence
from workbench.awt.reporting import (
    active_users,
    annual_working_time,
    working_time_by_week,
)
from workbench.tools.api import (
    DateRangeFilter,
    Days,
    Hours,
    Percentage,
    Serialized,
    date_range,
    raise_form_errors,
)


router = Router(tags=["absences"])


class AbsenceOut(Schema):
    id: int | None
    url: str | None
    user: str
    starts_on: dt.date
    ends_on: dt.date | None
    days: Decimal
    reason: str
    description: str


class AbsenceFilter(DateRangeFilter):
    user: str | None = None
    reason: (
        Literal["vacation", "sickness", "paid", "school", "other", "correction"] | None
    ) = None


@router.get("/absences/", response=list[AbsenceOut])
@paginate
def absence_list(request, filters: Query[AbsenceFilter]):
    """Absences overlapping the period (or from ``since`` until ``until``), oldest
    first"""
    absences = Absence.objects.select_related("user")
    if filters.user:
        absences = absences.filter(user___short_name__iexact=filters.user)
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
        "reason": absence.get_reason_display(),
        "description": absence.description,
    }


class AbsenceIn(Schema):
    user: str | None = Field(
        default=None, description="Short name, defaults to the authenticated user."
    )
    starts_on: dt.date
    ends_on: dt.date | None = Field(
        default=None, description="In the same year, empty for a single day."
    )
    days: Decimal = Field(gt=0, description="Working days, e.g. 0.5.")
    reason: Literal["vacation", "sickness", "paid", "school", "other", "correction"]
    description: str = Field(min_length=1)


@router.post("/absences/", response=AbsenceOut)
def absence_create(request, data: AbsenceIn, *, dry_run: bool = False):
    """Create an absence, validated like in the web interface

    Warnings of the web interface are errors here; nothing is saved if
    anything is invalid or with ``dry_run``."""
    user = request.user
    if data.user is not None:
        user = User.objects.filter(_short_name__iexact=data.user).first()
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
    if not form.is_valid():
        raise_form_errors(form)
    with transaction.atomic():
        absence = form.save()
        result = _absence_out(absence, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
    return result


class WorkingTimeFilter(Schema):
    year: int | None = None
    user: str | None = None
    all: bool = False
    weekly: bool = False


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
    months: list[WorkingTimeMonth]
    totals: WorkingTimeTotals
    weeks: list[WorkingTimeWeek] | None


class WorkingTime(Schema):
    year: int
    warnings: list[str]
    users: list[UserWorkingTime]


@router.get("/reports/working-time/", response=WorkingTime)
def working_time(request, filters: Query[WorkingTimeFilter]):
    """Annual working time of the authenticated user, of the user with the
    given short name, or of ``all`` users employed during the year (requires
    the controlling feature), like in the web interface

    Hours are per month: The target, logged hours, absences and their sum
    (working time) and the balance. The total balance includes the vacation
    days credit. ``weekly`` adds the hours per week until the current one."""
    year = filters.year or dt.date.today().year
    if filters.all:
        check_feature(request.user, FEATURES.CONTROLLING)
        users = list(active_users(year))
    elif filters.user:
        users = list(User.objects.filter(_short_name__iexact=filters.user))
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

    return {
        "year": year,
        "warnings": [str(warning) for warning in warnings],
        "users": [_user(row) for row in statistics["statistics"]],
    }
