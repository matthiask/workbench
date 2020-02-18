import datetime as dt

from django.utils.translation import gettext as _

from workbench.tools.validation import monday


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
