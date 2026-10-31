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
from workbench.contacts.api import OrganizationOut, organization_out
from workbench.invoices.api import InvoiceOut, invoice_out
from workbench.logbook.reporting import logbook_stats
from workbench.planning.reporting import planning_vs_logbook
from workbench.projects.api import ProjectSummary, project_summary
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
    Amount,
    DateRangeFilter,
    Days,
    Hours,
    Percentage,
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


# The old URLs keep working for integrations, but aren't documented anymore
@router.get("/key-data/", include_in_schema=False)
@router.get("/reports/key-data/")
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


@router.get("/cash-data/", include_in_schema=False)
@router.get("/reports/cash-data/")
def cash_data_api(request, date: dt.date | None = None):
    """Cash data as of the given date, today by default"""
    return jsonable(cash_data(date or dt.date.today()))


# The reports below are for users only, with the features of the web
# interface's reports. The static token is for the integrations above.
CONTROLLING = user_auth(feature=FEATURES.CONTROLLING)


def _user(user):
    return user.get_short_name()


# The web interface's form fields and their names in the API
FORM_FIELDS = {
    "cutoff_date": ["date"],
    "s": ["filter"],
    "closed_during_the_last_year": ["closed"],
}


def _form(form_class, request, data):
    """Validate the filters with the web interface's form"""
    form = form_class({k: v for k, v in data.items() if v is not None}, request=request)
    if not form.is_valid():
        raise ValidationError([
            {"loc": ["query", "filters", *error["loc"][2:]], "msg": error["msg"]}
            for error in form_errors(form, fields=FORM_FIELDS)
        ])
    return form


def _month(month):
    return f"{month[0]}-{month[1]:02d}"


class ProjectedProject(Schema):
    project: ProjectSummary
    owned_by: str
    projected_total: Amount
    gross_margin: Amount
    not_invoiced: Amount
    monthly: dict[str, Amount]


class ProjectedGrossMargin(Schema):
    monthly: dict[str, Amount]
    projects: list[ProjectedProject]


@router.get(
    "/reports/projected-gross-margin/",
    response=ProjectedGrossMargin,
    auth=CONTROLLING,
)
def projected_gross_margin(request):
    """Planned invoicing of open projects which hasn't been invoiced yet, by
    month (gross margin, third party costs are not included)"""
    data = key_data_module.projected_gross_margin()
    return {
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
    }


class BudgetFilter(Schema):
    date: dt.date | None = None
    owned_by: str | None = None
    internal: bool = False
    closed: bool = False
    filter: (
        Literal[
            "no-invoices", "maintenance", "old-projects", "no-projected-gross-margin"
        ]
        | None
    ) = None


class BudgetFigures(Schema):
    logbook: Amount
    cost: Amount
    effort_cost: Amount
    effort_hours_with_rate_undefined: Hours
    third_party_costs: Amount
    sold: Amount
    discount: Amount
    invoiced: Amount
    hours: Hours
    service_hours: Hours
    projected_gross_margin: Amount
    projected_gross_margin_on_cutoff_date: Amount


class BudgetProject(BudgetFigures):
    project: ProjectSummary
    owned_by: str
    closed_on: dt.date | None
    delta: Amount


class BudgetOverall(BudgetFigures):
    delta_positive: Amount
    delta_negative: Amount
    delta_beyond_offer: Amount
    delta_planned: Amount


class Budget(Schema):
    date: dt.date
    overall: BudgetOverall
    projects: list[BudgetProject]


@router.get("/reports/budget/", response=Budget, auth=CONTROLLING)
def budget(request, filters: Query[BudgetFilter]):
    """Project budget statistics: Logged effort and costs compared to what has
    been offered and invoiced, per open project on the cutoff ``date`` (today
    by default), or per project ``closed`` during the last year. ``owned_by``
    is a short name, or ``inactive`` for projects of inactive users.
    ``delta`` is the logbook minus the invoiced amount: work which hasn't been
    invoiced yet if positive, accruals if negative."""
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
            "cutoff_date": filters.date,
            "owned_by": owned_by,
            "internal": filters.internal or None,
            "closed_during_the_last_year": filters.closed or None,
            "s": filters.filter,
        },
    )
    statistics = project_budget_statistics.project_budget_statistics(
        form.queryset(), cutoff_date=form.cleaned_data.get("cutoff_date")
    )
    return {
        "date": statistics["cutoff_date"],
        "overall": statistics["overall"],
        "projects": [
            row
            | {
                "project": project_summary(row["project"], request),
                "owned_by": _user(row["project"].owned_by),
                "closed_on": row["project"].closed_on,
            }
            for row in statistics["statistics"]
        ],
    }


class ThirdPartyCostsFilter(Schema):
    this_year: bool = False


class LoggedThirdPartyCosts(Schema):
    past: Amount
    future: Amount


class ThirdPartyCostsProject(Schema):
    project: ProjectSummary
    owned_by: str
    offered: Amount
    logged: LoggedThirdPartyCosts
    invoiced: Amount
    delta: Amount


class ThirdPartyCosts(Schema):
    total_not_invoiced: Amount
    total_invoiced_too_much: Amount
    total_offered: Amount
    total_logged: LoggedThirdPartyCosts
    total_invoiced: Amount
    projects: list[ThirdPartyCostsProject]


@router.get("/reports/third-party-costs/", response=ThirdPartyCosts, auth=CONTROLLING)
def third_party_costs_api(request, filters: Query[ThirdPartyCostsFilter]):
    """Third party costs logged and invoiced per open project (or also closed
    during the current year); ``delta`` is positive for costs which haven't
    been invoiced yet. Logged costs are split into the past and the future."""
    form = _form(
        PlayingBankForm, request, {"s": "this-year" if filters.this_year else ""}
    )
    statistics = third_party_costs.playing_bank(projects=form.queryset())
    return {
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
    }


class CutoffFilter(Schema):
    date: dt.date | None = None


class OpenItemsWeek(Schema):
    week: dt.date
    total_excl_tax: Amount
    total: Amount


class OpenItems(Schema):
    date: dt.date
    total_excl_tax: Amount
    total: Amount
    weeks: list[OpenItemsWeek]
    invoices: list[InvoiceOut]


@router.get("/reports/open-items/", response=OpenItems, auth=CONTROLLING)
def open_items(request, filters: Query[CutoffFilter]):
    """Invoices which have been sent but not paid on the cutoff ``date`` (today
    by default), with totals per week of their due date"""
    form = _form(OpenItemsForm, request, {"cutoff_date": filters.date})
    data = form.open_items_list()
    return {
        "date": form.cleaned_data["cutoff_date"],
        "total_excl_tax": data["total_excl_tax"],
        "total": data["total"],
        "weeks": [{"week": week} | totals for week, totals in data["weeks"]],
        "invoices": [invoice_out(invoice, request) for invoice in data["list"]],
    }


class PeriodFilter(DateRangeFilter, UsersFilter):
    pass


class Period(Schema):
    since: dt.date
    until: dt.date


def _this_week():
    return [monday(), monday() + dt.timedelta(days=6)]


class CustomerHours(Schema):
    customer: OrganizationOut
    total_hours: Hours
    users: dict[str, Hours]


class HoursPerCustomer(Period):
    total_hours: Hours
    users: dict[str, Hours]
    customers: list[CustomerHours]


# Not restricted in the web interface either
@router.get("/reports/hours-per-customer/", response=HoursPerCustomer, auth=user_auth())
def hours_per_customer_api(request, filters: Query[PeriodFilter]):
    """Logged hours per customer and user, this week by default"""
    period = date_range(filters, default=_this_week())
    stats = hours_per_customer(period, users=filter_users(filters))
    return {
        "since": period[0],
        "until": period[1],
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
    }


class TypeHours(Schema):
    type: str
    hours: Hours
    expected_percentage: Percentage
    reached_percentage: Percentage


class HoursSplit(Schema):
    total: Hours
    external: Hours
    internal: Hours


class UserTypeHours(HoursSplit):
    user: str
    types: list[TypeHours]


class HoursPerType(Period):
    total: HoursSplit
    users: list[UserTypeHours]


@router.get("/reports/hours-per-type/", response=HoursPerType, auth=CONTROLLING)
def hours_per_type_api(request, filters: Query[PeriodFilter]):
    """Logged hours per user, external and per internal type, with the
    expected and reached percentages, this week by default"""
    period = date_range(filters, default=_this_week())
    stats = hours_per_type(period, users=filter_users(filters))
    return {
        "since": period[0],
        "until": period[1],
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
    }


class GreenHoursRow(Schema):
    profitable: Hours
    overdrawn: Hours
    maintenance: Hours
    internal: Hours
    total: Hours
    percentage: Percentage
    external_percentage: Percentage


class UserGreenHours(GreenHoursRow):
    user: str


class GreenHours(Period):
    total: GreenHoursRow | None
    users: list[UserGreenHours]


@router.get("/reports/green-hours/", response=GreenHours, auth=CONTROLLING)
def green_hours_api(request, filters: Query[PeriodFilter]):
    """Logged hours per user: profitable (within the budget), overdrawn
    (beyond the budget), maintenance and internal, this week by default"""
    period = date_range(filters, default=_this_week())
    rows = green_hours(period, users=filter_users(filters))
    return {
        "since": period[0],
        "until": period[1],
        "total": next((rec for user, rec in rows if user == 0), None),
        "users": [{"user": _user(user)} | rec for user, rec in rows if user != 0],
    }


class PlanningWeek(Schema):
    week: dt.date
    planned: Hours | None
    logged: Hours | None


class CustomerPlanning(Schema):
    customer: OrganizationOut
    planned: Hours
    logged: Hours
    diff: Hours
    allocation: Percentage | None
    weeks: list[PlanningWeek]


class PlanningVsLogbook(Period):
    planned: Hours
    logged: Hours
    diff: Hours
    logged_percentage: Percentage | None
    customers: list[CustomerPlanning]


# Not restricted in the web interface either
@router.get(
    "/reports/planning-vs-logbook/", response=PlanningVsLogbook, auth=user_auth()
)
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

    return {
        "since": period[0],
        "until": period[1],
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
    }


class LoggedHoursStats(Schema):
    count: int
    sum: Hours
    avg: Hours | None


class InsufficientBreaksTotal(Schema):
    days_count: int
    of: int


class InsufficientBreaks(Schema):
    days: list[dt.date]
    of: int
    warning: bool


class UserLogging(Schema):
    user: str
    logged_hours: LoggedHoursStats
    mean_logging_delay_hours: Hours
    logging: str
    insufficient_breaks: InsufficientBreaks


class Logging(Period):
    logged_hours: LoggedHoursStats
    insufficient_breaks: InsufficientBreaksTotal
    users: list[UserLogging]


@router.get("/reports/logging/", response=Logging, auth=CONTROLLING)
def logging_api(request, filters: Query[DateRangeFilter]):
    """How and when users log their hours, this week by default. The delay is
    the average time in hours between noon of the day the work was done and
    logging it; insufficient breaks are days with too short breaks for the
    hours worked."""
    period = date_range(filters, default=_this_week())
    stats = logbook_stats(period)
    return {
        "since": period[0],
        "until": period[1],
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
    }


class SqueezeContribution(Schema):
    hours: Hours
    invoiced_hours: Hours
    gross_margin: Amount
    rate: Amount
    hours_rate_unknown: Hours


class SqueezeUserProject(SqueezeContribution):
    project: ProjectSummary


class SqueezeFigures(Schema):
    employment_percentage: Percentage
    absence_days: Days
    gross_margin: Amount
    hours_in_range: Hours
    rate: Amount
    internal_hours: Hours
    external_hours: Hours
    total_hours: Hours
    external_percentage: Percentage
    invoiced_per_external_hour: Amount
    expected_gross_margin: Amount
    delta: Amount


class SqueezeUser(SqueezeFigures):
    user: str
    specialist_field: str | None
    invoiced_hours_in_range: Hours
    profitable_percentage: Percentage
    expected_hourly_rate: Amount
    hours_rate_unknown: Hours
    projects: list[SqueezeUserProject]


class SqueezeProject(Schema):
    project: ProjectSummary
    offered: Amount
    projected: Amount
    invoiced: Amount
    gross_margin: Amount
    hours_offered: Hours
    hours_logged: Hours
    hours: Hours
    rate: Amount
    hours_in_range: Hours
    invoiced_hours_in_range: Hours
    gross_margin_in_range: Amount
    hours_rate_unknown: Hours
    users: dict[str, SqueezeContribution]


class SqueezeCustomer(Schema):
    customer: OrganizationOut
    gross_margin: Amount
    hours_in_range: Hours
    rate: Amount


class SqueezeField(Schema):
    name: str
    users: str
    gross_margin: Amount
    hours_in_range: Hours
    rate: Amount
    external_percentage: Percentage


class Squeeze(Period):
    may_be_incomplete: bool
    default_hourly_rate: Amount
    totals: SqueezeFigures
    users: list[SqueezeUser]
    projects: list[SqueezeProject]
    customers: list[SqueezeCustomer]
    specialist_fields: list[SqueezeField]


@router.get(
    "/reports/squeeze/",
    response=Squeeze,
    auth=user_auth(feature=FEATURES.PRODUCTIVITY),
)
def squeeze_api(request, filters: Query[DateRangeFilter]):
    """Gross margin per user and project, the last month by default. Projects'
    gross margins are split between users by the value of their work (invoiced
    hours times the hourly rate), rates use the hours spent. Invoices of a period may be incomplete until the 9th of the
    following month."""
    period = date_range(filters, default=last_month_range())
    data = squeeze.squeeze_data(period)
    return {
        "since": period[0],
        "until": period[1],
        # Like the web interface's warning
        "may_be_incomplete": dt.date.today()
        < (period[1].replace(day=1) + dt.timedelta(days=32)).replace(day=9),
        "default_hourly_rate": data["default_hourly_rate"],
        "totals": data["totals"],
        "users": [
            row
            | {
                "user": _user(row["user"]),
                "projects": [
                    contrib | {"project": project_summary(project, request)}
                    for project, contrib in row["by_project"].items()
                ],
            }
            for row in data["users"]
        ],
        "projects": [
            row
            | {
                "project": project_summary(row["project"], request),
                "users": {
                    _user(user): contrib for user, contrib in row["by_user"].items()
                },
            }
            for row in data["projects"]
        ],
        "customers": [
            row | {"customer": organization_out(row["organization"], request)}
            for row in data["organizations"]
        ],
        "specialist_fields": data["fields"],
    }
