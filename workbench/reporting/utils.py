import datetime as dt
from collections import defaultdict

from django.db.models import Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils.translation import gettext as _

from workbench.tools.formats import Z1, Z2
from workbench.tools.validation import monday


def sum_of(queryset, field="total_excl_tax", *, default=Z2):
    """Sum of ``field`` over ``queryset``, ``default`` if there are no rows"""
    return queryset.order_by().aggregate(s=Sum(field))["s"] or default


def sum_by_project(queryset, field="total_excl_tax", *, project="project", default=Z2):
    """``{project_id: sum of field}``, ``default`` for projects without rows"""
    return defaultdict(
        lambda: default,
        queryset
        .order_by()
        .values(project)
        .annotate(s=Sum(field))
        .values_list(project, "s"),
    )


def date_ranges():
    this_month = dt.date.today().replace(day=1)
    last_month = (this_month - dt.timedelta(days=1)).replace(day=1)
    next_month = (this_month + dt.timedelta(days=31)).replace(day=1)

    this_quarter = dt.date(this_month.year, 1 + (this_month.month - 1) // 3 * 3, 1)
    last_quarter = (this_quarter - dt.timedelta(days=75)).replace(day=1)
    next_quarter = (this_quarter + dt.timedelta(days=105)).replace(day=1)

    return [
        (
            (monday() + dt.timedelta(days=0)).isoformat(),
            (monday() + dt.timedelta(days=6)).isoformat(),
            _("this week"),
        ),
        (
            (monday() - dt.timedelta(days=7)).isoformat(),
            (monday() - dt.timedelta(days=1)).isoformat(),
            _("last week"),
        ),
        (
            this_month.isoformat(),
            (next_month - dt.timedelta(days=1)).isoformat(),
            _("this month"),
        ),
        (
            last_month.isoformat(),
            (this_month - dt.timedelta(days=1)).isoformat(),
            _("last month"),
        ),
        (
            this_quarter.isoformat(),
            (next_quarter - dt.timedelta(days=1)).isoformat(),
            _("this quarter"),
        ),
        (
            last_quarter.isoformat(),
            (this_quarter - dt.timedelta(days=1)).isoformat(),
            _("last quarter"),
        ),
        (
            dt.date(this_month.year, 1, 1).isoformat(),
            dt.date(this_month.year, 12, 31).isoformat(),
            _("this year"),
        ),
        (
            dt.date(this_month.year - 1, 1, 1).isoformat(),
            dt.date(this_month.year - 1, 12, 31).isoformat(),
            _("last year"),
        ),
    ]


def sum_by_month(queryset, date_field, field="total_excl_tax"):
    """``{(year, month): sum of field}`` grouped by the month of ``date_field``"""
    return defaultdict(
        lambda: Z2,
        {
            (year, month): total
            for year, month, total in queryset
            .order_by()
            .annotate(year=ExtractYear(date_field), month=ExtractMonth(date_field))
            .values("year", "month")
            .annotate(s=Sum(field))
            .values_list("year", "month", "s")
        },
    )


def effort_cost_by_project(logged_hours):
    """Hours times the service's effort rate per project as
    ``{project_id: {"cost": ..., "hours_rate_undefined": ..., "hours": ...}}``.

    Hours on services without an effort rate aren't valued, they are only
    reported in ``hours_rate_undefined``."""
    projects = defaultdict(
        lambda: {"cost": Z2, "hours_rate_undefined": Z1, "hours": Z1}
    )
    for project, rate, hours in (
        logged_hours
        .order_by()
        .values("service__project", "service__effort_rate")
        .annotate(s=Sum("hours"))
        .values_list("service__project", "service__effort_rate", "s")
    ):
        if rate is None:
            projects[project]["hours_rate_undefined"] += hours
        else:
            projects[project]["cost"] += rate * hours
        projects[project]["hours"] += hours
    return projects
