import datetime as dt
import secrets
from typing import Literal

from django.conf import settings
from django.utils.translation import gettext as _
from ninja import Query, Router, Schema
from ninja.errors import ValidationError
from ninja.security import HttpBearer

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.contacts.api import organization_out
from workbench.invoices.api import invoice_out
from workbench.logbook.reporting import logbook_stats
from workbench.planning.reporting import planning_vs_logbook
from workbench.projects.api import project_summary
from workbench.projects.reporting import hours_per_customer, hours_per_type
from workbench.reporting import (
    key_data as key_data_module,
    project_budget_statistics,
    squeeze,
    third_party_costs,
)
from workbench.reporting.cash_data_api import cash_data
from workbench.reporting.green_hours import green_hours
from workbench.reporting.key_data_api import key_data_for_month
from workbench.reporting.views import (
    OpenItemsForm,
    PlayingBankForm,
    ProjectBudgetStatisticsForm,
)
from workbench.tools.api import (
    DateRangeFilter,
    UsersFilter,
    date_range,
    filter_users,
    form_errors,
)
from workbench.tools.validation import last_month_range, monday


def jsonable(value):
    """Convert report data to JSON: dates as ISO strings, decimals as numbers"""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dt.date):
        return value.isoformat()
    if value is None or isinstance(value, (str, int)):
        return value
    return float(value)


class ReportingToken(HttpBearer):
    """The reporting APIs authenticate with a static bearer token"""

    def authenticate(self, request, token):
        expected = settings.KEY_DATA_API_TOKEN
        return bool(expected) and secrets.compare_digest(
            token.encode(), expected.encode()
        )


# The static token for integrations, or users with the controlling feature
# like in the web interface
router = Router(
    auth=[ReportingToken(), *user_auth(feature=FEATURES.CONTROLLING)],
    tags=["reporting"],
)


@router.get("/key-data/")
def key_data(request, month: str | None = None):
    """Key data of the given month (2026-09), the last month by default"""
    if month:
        try:
            first = dt.datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            raise ValidationError([
                {"loc": ["query", "month"], "msg": _("Expected a month like 2026-09.")}
            ]) from None
    else:
        first = last_month_range()[0]
    return jsonable(key_data_for_month(first))


@router.get("/cash-data/")
def cash_data_api(request, date: dt.date | None = None):
    """Cash data as of the given date, today by default"""
    return jsonable(cash_data(date or dt.date.today()))


# The reports below are for users only, with the features of the web
# interface's reports. The static token is for the integrations above.
CONTROLLING = user_auth(feature=FEATURES.CONTROLLING)


def _user(user):
    return user.get_short_name()


def _form(form_class, request, data):
    form = form_class({k: v for k, v in data.items() if v is not None}, request=request)
    if not form.is_valid():
        raise ValidationError([
            {"loc": ["query", "filters", *error["loc"][2:]], "msg": error["msg"]}
            for error in form_errors(form)
        ])
    return form


def _month(month):
    return f"{month[0]}-{month[1]:02d}"


@router.get("/projected-gross-margin/", auth=CONTROLLING)
def projected_gross_margin(request):
    """Planned invoicing of open projects which hasn't been invoiced yet, by
    month (gross margin, third party costs are not included)"""
    data = key_data_module.projected_gross_margin()
    return jsonable({
        "monthly": {
            _month(month): value
            for month, value in sorted(data["monthly_overall"].items())
        },
        "projects": [
            {
                "project": project_summary(row["project"], request),
                "owned_by": _user(row["project"].owned_by),
                "projected_total": row["projected_total"],
                "gross_margin": row["gross_margin"],
                "not_invoiced": row["delta"],
                "monthly": {
                    _month(month): value
                    for month, value in sorted(row["monthly"].items())
                },
            }
            for row in sorted(data["projects"], key=lambda row: -row["delta"])
        ],
    })


class BudgetFilter(Schema):
    cutoff_date: dt.date | None = None
    owned_by: str | None = None
    internal: bool = False
    closed_during_the_last_year: bool = False
    s: (
        Literal[
            "no-invoices", "maintenance", "old-projects", "no-projected-gross-margin"
        ]
        | None
    ) = None


@router.get("/project-budget-statistics/", auth=CONTROLLING)
def project_budget_statistics_api(request, filters: Query[BudgetFilter]):
    """Logged effort and costs compared to what has been offered and invoiced,
    per project. ``owned_by`` is a short name, or ``inactive`` for projects of
    inactive users. ``delta`` is the logbook minus the invoiced amount: work
    which hasn't been invoiced yet if positive, accruals if negative."""
    owned_by = None
    if filters.owned_by == "inactive":
        owned_by = 0
    elif filters.owned_by:
        user = User.objects.filter(_short_name__iexact=filters.owned_by).first()
        owned_by = user.id if user else -2
    form = _form(
        ProjectBudgetStatisticsForm,
        request,
        {
            "cutoff_date": filters.cutoff_date,
            "owned_by": owned_by,
            "internal": filters.internal or None,
            "closed_during_the_last_year": filters.closed_during_the_last_year or None,
            "s": filters.s,
        },
    )
    statistics = project_budget_statistics.project_budget_statistics(
        form.queryset(), cutoff_date=form.cleaned_data.get("cutoff_date")
    )
    return jsonable({
        "cutoff_date": statistics["cutoff_date"],
        "overall": statistics["overall"],
        "projects": [
            {
                "project": project_summary(row["project"], request),
                "owned_by": _user(row["project"].owned_by),
                "closed_on": row["project"].closed_on,
            }
            | {key: value for key, value in row.items() if key != "project"}
            for row in statistics["statistics"]
        ],
    })


class ThirdPartyCostsFilter(Schema):
    this_year: bool = False


@router.get("/third-party-costs/", auth=CONTROLLING)
def third_party_costs_api(request, filters: Query[ThirdPartyCostsFilter]):
    """Third party costs logged and invoiced per open project (or also closed
    during the current year); ``delta`` is positive for costs which haven't
    been invoiced yet. Logged costs are split into the past and the future."""
    form = _form(
        PlayingBankForm, request, {"s": "this-year" if filters.this_year else ""}
    )
    statistics = third_party_costs.playing_bank(projects=form.queryset())
    return jsonable({
        "total_not_invoiced": statistics["total_plus"],
        "total_invoiced_too_much": statistics["total_minus"],
        "total_offered": statistics["total_offered"],
        "total_logged": statistics["total_logged"],
        "total_invoiced": statistics["total_invoiced"],
        "projects": [
            {
                "project": project_summary(row["project"], request),
                "owned_by": _user(row["project"].owned_by),
                "offered": row["offered"],
                "logged": row["logged"],
                "invoiced": row["invoiced"],
                "delta": row["delta"],
            }
            for row in sorted(statistics["projects"], key=lambda row: -row["delta"])
        ],
    })


@router.get("/open-items/", auth=CONTROLLING)
def open_items(request, cutoff_date: dt.date | None = None):
    """Invoices which have been sent but not paid on the cutoff date (today by
    default), with totals per week of their due date"""
    form = _form(OpenItemsForm, request, {"cutoff_date": cutoff_date})
    data = form.open_items_list()
    return jsonable({
        "cutoff_date": form.cleaned_data["cutoff_date"],
        "total_excl_tax": data["total_excl_tax"],
        "total": data["total"],
        "weeks": [{"week": week} | totals for week, totals in data["weeks"]],
    }) | {
        # Like the invoices API
        "invoices": [invoice_out(invoice, request) for invoice in data["list"]],
    }


class PeriodFilter(DateRangeFilter, UsersFilter):
    pass


def _this_week():
    return [monday(), monday() + dt.timedelta(days=6)]


# Not restricted in the web interface either
@router.get("/hours-per-customer/", auth=user_auth())
def hours_per_customer_api(request, filters: Query[PeriodFilter]):
    """Logged hours per customer and user, this week by default"""
    period = date_range(filters, default=_this_week())
    stats = hours_per_customer(period, users=filter_users(filters))
    return jsonable({
        "date_from": period[0],
        "date_until": period[1],
        "total_hours": stats["total_hours"],
        "users": {_user(user): hours for user, hours in stats["user_hours"]},
        "customers": [
            {
                "customer": organization_out(row["organization"], request),
                "total_hours": row["total_hours"],
                "users": {
                    _user(user): hours for user, hours in row["user_hours"] if hours
                },
            }
            for row in stats["organizations"]
        ],
    })


@router.get("/hours-per-type/", auth=CONTROLLING)
def hours_per_type_api(request, filters: Query[PeriodFilter]):
    """Logged hours per user, external and per internal type, with the
    expected and reached percentages, this week by default"""
    period = date_range(filters, default=_this_week())
    stats = hours_per_type(period, users=filter_users(filters))
    return jsonable({
        "date_from": period[0],
        "date_until": period[1],
        "total": stats["total"],
        "users": [
            {
                "user": _user(row["user"]),
                "total": row["total"],
                "external": row["external"],
                "internal": row["internal"],
                "types": [
                    {
                        "type": str(getattr(type["type"], "name", type["type"])),
                        "hours": type["hours"],
                        "expected_percentage": type["expected"],
                        "reached_percentage": type["reached"],
                    }
                    for type in row["hours_per_type"]
                ],
            }
            for row in stats["users"]
        ],
    })


@router.get("/green-hours/", auth=CONTROLLING)
def green_hours_api(request, filters: Query[PeriodFilter]):
    """Logged hours per user: profitable (within the budget), overdrawn
    (beyond the budget), maintenance and internal, this week by default"""
    period = date_range(filters, default=_this_week())
    rows = green_hours(period, users=filter_users(filters))
    return jsonable({
        "date_from": period[0],
        "date_until": period[1],
        "total": next((rec for user, rec in rows if user == 0), None),
        "users": [{"user": _user(user)} | rec for user, rec in rows if user != 0],
    })


# Not restricted in the web interface either
@router.get("/planning-vs-logbook/", auth=user_auth())
def planning_vs_logbook_api(request, filters: Query[PeriodFilter]):
    """Planned and logged hours per customer and week, this week by default.
    ``allocation`` is the customer's share of the logged hours relative to its
    share of the planned hours in percent."""
    period = date_range(filters, default=_this_week())
    stats = planning_vs_logbook(
        period, users=filter_users(filters) or User.objects.all()
    )

    def _week(week):
        return week.date() if isinstance(week, dt.datetime) else week

    return jsonable({
        "date_from": period[0],
        "date_until": period[1],
        "planned": stats["planned"],
        "logged": stats["logged"],
        "diff": stats["diff"],
        "logged_percentage": stats["overall_ratio"],
        "customers": [
            {
                "customer": organization_out(row["customer"], request),
                "planned": row["planned"],
                "logged": row["logged"],
                "diff": row["diff"],
                "allocation": row["allocation"],
                "weeks": [
                    {
                        "week": _week(week["week"]),
                        "planned": week["planned"],
                        "logged": week["logged"],
                    }
                    for week in row["per_week"]
                    if week["planned"] or week["logged"]
                ],
            }
            for row in stats["per_customer"]
        ],
    })


@router.get("/logging/", auth=CONTROLLING)
def logging_api(request, filters: Query[DateRangeFilter]):
    """How and when users log their hours, this week by default. The delay is
    the average time in hours between noon of the day the work was done and
    logging it; insufficient breaks are days with too short breaks for the
    hours worked."""
    period = date_range(filters, default=_this_week())
    stats = logbook_stats(period)
    return jsonable({
        "date_from": period[0],
        "date_until": period[1],
        "logged_hours": stats["logged_hours_stats"],
        "insufficient_breaks": stats["insufficient_breaks"],
        "users": [
            {
                "user": _user(row["user"]),
                "logged_hours": row["logged_hours_stats"],
                "mean_logging_delay_hours": row["mean_logging_delay"]["delay"],
                "logging": str(row["mean_logging_delay"]["classification"][0]),
                "insufficient_breaks": {
                    "days": row["insufficient_breaks"]["days"],
                    "of": row["insufficient_breaks"]["of"],
                    "warning": row["insufficient_breaks"]["danger"],
                },
            }
            for row in sorted(stats["users"], key=lambda row: row["user"])
        ],
    })


@router.get("/squeeze/", auth=user_auth(feature=FEATURES.PRODUCTIVITY))
def squeeze_api(request, filters: Query[DateRangeFilter]):
    """Gross margin per user and project, the last month by default. Projects'
    gross margins are split between users by hours weighted with the hourly
    rate. Invoices of a period may be incomplete until the 9th of the
    following month."""
    period = date_range(filters, default=last_month_range())
    data = squeeze.squeeze_data(period)
    user_keys = [
        "employment_percentage",
        "gross_margin",
        "hours_in_range",
        "rate",
        "internal_hours",
        "external_hours",
        "total_hours",
        "external_percentage",
        "profitable_percentage",
        "expected_hourly_rate",
        "expected_gross_margin",
        "delta",
        "absence_days",
        "hours_rate_unknown",
    ]
    project_keys = [
        "offered",
        "projected",
        "invoiced",
        "gross_margin",
        "hours_offered",
        "hours_logged",
        "hours",
        "rate",
        "hours_in_range",
        "gross_margin_in_range",
        "hours_rate_unknown",
    ]
    contribution_keys = ["hours", "gross_margin", "rate", "hours_rate_unknown"]
    return jsonable({
        "date_from": period[0],
        "date_until": period[1],
        # Like the web interface's warning
        "may_be_incomplete": dt.date.today()
        < (period[1].replace(day=1) + dt.timedelta(days=32)).replace(day=9),
        "default_hourly_rate": data["default_hourly_rate"],
        "totals": data["totals"],
        "users": [
            {"user": _user(row["user"]), "specialist_field": row["specialist_field"]}
            | {key: row[key] for key in user_keys}
            | {
                "projects": [
                    {"project": project_summary(project, request)}
                    | {key: contrib[key] for key in contribution_keys}
                    for project, contrib in row["by_project"].items()
                ]
            }
            for row in data["users"]
        ],
        "projects": [
            {"project": project_summary(row["project"], request)}
            | {key: row[key] for key in project_keys}
            | {
                "users": {
                    _user(user): {key: contrib[key] for key in contribution_keys}
                    for user, contrib in row["by_user"].items()
                }
            }
            for row in data["projects"]
        ],
        "customers": [
            {
                "customer": organization_out(row["organization"], request),
                "gross_margin": row["gross_margin"],
                "hours_in_range": row["hours_in_range"],
                "rate": row["rate"],
            }
            for row in data["organizations"]
        ],
        "specialist_fields": data["fields"],
    })
