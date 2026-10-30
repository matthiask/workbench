import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db.models import Q
from django.utils.translation import gettext as _
from ninja import Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import check_feature
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.awt.reporting import (
    active_users,
    annual_working_time,
    working_time_by_week,
)
from workbench.reporting.api import jsonable
from workbench.tools.api import DateRangeFilter, Serialized, date_range


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
        lambda absence: {
            "id": absence.id,
            "url": request.build_absolute_uri(absence.get_absolute_url()),
            "user": absence.user.get_short_name(),
            "starts_on": absence.starts_on,
            "ends_on": absence.ends_on,
            "days": absence.days,
            "reason": absence.get_reason_display(),
            "description": absence.description,
        },
    )


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
TOTALS = [
    "percentage",
    "target",
    "hours",
    "absences_time",
    "working_time",
    "running_sum",
    "available_vacation_days",
    "absence_vacation",
    "vacation_days_correction",
    "vacation_days_credit",
    "balance",
    "balance_days",
    "absence_sickness",
    "absence_paid",
    "absence_school",
    "absence_correction",
    "holiday_public",
    "holiday_company",
]


@router.get("/reports/working-time/")
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
            "totals": {key: row["totals"][key] for key in TOTALS},
            "weeks": working_time_by_week(year, user=row["user"])
            if filters.weekly
            else None,
        }

    return jsonable({
        "year": year,
        "warnings": [str(warning) for warning in warnings],
        "users": [_user(row) for row in statistics["statistics"]],
    })
