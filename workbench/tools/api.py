import datetime as dt
import re

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _
from ninja import Schema
from ninja.errors import ValidationError as NinjaValidationError

from workbench.accounts.models import Team, User
from workbench.tools.validation import monday


def full_clean(instance, loc, errors, *, exclude=()):
    """Validate the model instance, add errors located at ``loc`` to
    ``errors``"""
    try:
        instance.full_clean(exclude=exclude)
    except ValidationError as exc:
        errors.extend(
            {"loc": [*loc, field], "msg": message}
            for field, messages in exc.message_dict.items()
            for message in messages
        )


def form_errors(form, *, fields=None):
    """Errors of the invalid form; warnings of the web interface are errors
    too

    ``fields`` maps form fields to their location in the request body."""
    fields = fields or {}
    return [
        {
            "loc": ["body", "data"]
            + ([] if field == "__all__" else fields.get(field, [field])),
            "msg": message,
        }
        for field, messages in form.errors.items()
        for message in messages
    ] + [
        {"loc": ["body", "data"], "msg": str(warning)}
        for warning in form.warnings.values()
    ]


def raise_form_errors(form, *, fields=None):
    raise NinjaValidationError(form_errors(form, fields=fields))


PERIOD = re.compile(
    r"^(?P<year>\d{4})(?:-(?:(?P<month>\d{1,2})|[qQ](?P<quarter>[1-4])))?$"
)
RELATIVE_PERIOD = re.compile(
    r"^(?P<offset>last|this|next)-(?P<unit>week|month|quarter|year)$"
)
OFFSETS = {"last": -1, "this": 0, "next": 1}


class DateRangeFilter(Schema):
    """``period`` is a year (2026), a month (2026-09), a quarter (2026-Q3) or
    relative like last-week, this-month, next-quarter or last-year;
    ``date_from`` and ``date_until`` override its start and end"""

    period: str | None = None
    date_from: dt.date | None = None
    date_until: dt.date | None = None


def _months(first, count):
    """The first and the last day of ``count`` months starting at ``first``"""
    index = first.year * 12 + first.month - 1 + count
    return [first, dt.date(index // 12, index % 12 + 1, 1) - dt.timedelta(days=1)]


def _shift_months(day, months):
    index = day.year * 12 + day.month - 1 + months
    return dt.date(index // 12, index % 12 + 1, 1)


def _relative_period(offset, unit):
    today = dt.date.today()
    if unit == "week":
        first = monday() + dt.timedelta(days=7 * offset)
        return [first, first + dt.timedelta(days=6)]
    if unit == "month":
        return _months(_shift_months(today, offset), 1)
    if unit == "quarter":
        this = dt.date(today.year, today.month - (today.month - 1) % 3, 1)
        return _months(_shift_months(this, 3 * offset), 3)
    return [dt.date(today.year + offset, 1, 1), dt.date(today.year + offset, 12, 31)]


def _period(value):
    def error(msg):
        return NinjaValidationError([
            {"loc": ["query", "filters", "period"], "msg": msg}
        ])

    if match := RELATIVE_PERIOD.match(value):
        return _relative_period(OFFSETS[match["offset"]], match["unit"])
    if not (match := PERIOD.match(value)):
        raise error(
            _(
                "Expected a year, a month or a quarter like 2026-Q3, or a"
                " relative period like last-month."
            )
        )
    year = int(match["year"])
    if match["month"]:
        if not 1 <= int(match["month"]) <= 12:
            raise error(_("Invalid month."))
        return _months(dt.date(year, int(match["month"]), 1), 1)
    if match["quarter"]:
        return _months(dt.date(year, 3 * int(match["quarter"]) - 2, 1), 3)
    return [dt.date(year, 1, 1), dt.date(year, 12, 31)]


def date_range(filters, *, default):
    """The date range of a ``DateRangeFilter``, ``default`` without filters"""
    date_from, date_until = _period(filters.period) if filters.period else default
    date_from = filters.date_from or date_from
    date_until = filters.date_until or date_until
    if date_from > date_until:
        raise NinjaValidationError([
            {
                "loc": ["query", "filters", "date_until"],
                "msg": _("The end of the period must not be before its start."),
            }
        ])
    return [date_from, date_until]


class UsersFilter(Schema):
    """Short names of users or the name of a team, everyone by default"""

    user: list[str] = []
    team: str | None = None


def filter_users(filters):
    """The users of a ``UsersFilter``, ``None`` without filters"""
    if not filters.user and not filters.team:
        return None
    users = User.objects.all()
    if filters.team:
        try:
            team = Team.objects.get(name__iexact=filters.team)
        except Team.DoesNotExist:
            raise NinjaValidationError([
                {"loc": ["query", "filters", "team"], "msg": _("Unknown team.")}
            ]) from None
        users = users.filter(teams=team)
    if filters.user:
        q = Q()
        for short_name in filters.user:
            q |= Q(_short_name__iexact=short_name)
        users = users.filter(q)
        found = {user.get_short_name().casefold() for user in users}
        if unknown := [name for name in filters.user if name.casefold() not in found]:
            raise NinjaValidationError([
                {
                    "loc": ["query", "filters", "user"],
                    "msg": _("Unknown users: %s") % ", ".join(unknown),
                }
            ])
    return users
