import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _
from ninja import Query, Schema
from ninja.errors import ValidationError as NinjaValidationError
from ninja.pagination import LimitOffsetPagination
from pydantic import ConfigDict, Field, PlainSerializer

from workbench.accounts.models import Team, User
from workbench.tools.validation import monday


# Numbers of request bodies: JSON allows Infinity and NaN, and the decimal
# fields of the database have ten digits at most
Number = Annotated[float, Field(allow_inf_nan=False, gt=-1e10, lt=1e10)]


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


def form_errors(form, *, fields=None, ignore_warnings=()):
    """Errors of the invalid form; warnings of the web interface are errors
    too unless their code is in ``ignore_warnings``, they carry their code

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
        {"loc": ["body", "data"], "msg": str(warning), "code": code}
        for code, warning in form.warnings.items()
        if code not in ignore_warnings
    ]


def validate_form(form, *, fields=None, ignore_warnings=()):
    """Raise the errors of the form and its warnings which haven't been
    ignored explicitly, like the web interface does"""
    if not form.is_valid(ignore_warnings=True) or (
        set(form.warnings) - set(ignore_warnings)
    ):
        raise_form_errors(form, fields=fields, ignore_warnings=ignore_warnings)


IGNORE_WARNINGS = Query(
    [],
    description="Codes of warnings of the web interface to ignore, warnings"
    " are errors with their code otherwise.",
)


def form_data(form):
    """The data of an unbound form with the instance's current values, to
    change some of them and validate the result with the same form like the
    web interface does"""
    return {
        name: "" if (value := form[name].value()) is None else value
        for name in form.fields
    }


def raise_form_errors(form, *, fields=None, ignore_warnings=()):
    raise NinjaValidationError(
        form_errors(form, fields=fields, ignore_warnings=ignore_warnings)
    )


PERIOD = re.compile(
    r"^(?P<year>\d{4})(?:-(?:(?P<month>\d{1,2})|[qQ](?P<quarter>[1-4])))?$"
)
RELATIVE_PERIOD = re.compile(
    r"^(?P<offset>last|this|next)-(?P<unit>week|month|quarter|year)$"
)
OFFSETS = {"last": -1, "this": 0, "next": 1}


# Dates far away crash computations (and are mistakes anyway)
DATES = (dt.date(1900, 1, 1), dt.date(2999, 12, 31))


def dates_error(loc):
    """The validation error for dates outside of ``DATES``"""
    return NinjaValidationError([
        {
            "loc": loc,
            "msg": _("Dates have to be between %(min)s and %(max)s.")
            % {"min": DATES[0], "max": DATES[1]},
        }
    ])


# Common filters, with descriptions for the OpenAPI document
SearchQuery = Annotated[
    str, Field(description="Full text search like the web interface's lists.")
]
ShortName = Annotated[
    str | None,
    Field(description="Short name of a user, case-insensitive (see /api/users/)."),
]
OrganizationID = Annotated[int | None, Field(description="ID of the organization.")]
ProjectID = Annotated[int | None, Field(description="ID of the project.")]


class InputSchema(Schema):
    """Request bodies reject unknown fields: data under a wrong key (often
    from LLMs) would be lost silently"""

    model_config = ConfigDict(extra="forbid")


class DateRangeFilter(Schema):
    """``period`` is a year (2026), a month (2026-09), a quarter (2026-Q3) or
    relative like last-week, this-month, next-quarter or last-year;
    ``since`` and ``until`` override its start and end"""

    period: str | None = Field(
        default=None,
        description="A year (2026), a month (2026-09), a quarter (2026-Q3) or"
        " relative like last-week, this-month, next-quarter or last-year.",
    )
    since: dt.date | None = Field(
        default=None, description="Overrides the start of the period."
    )
    until: dt.date | None = Field(
        default=None, description="Overrides the end of the period."
    )


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
    if not DATES[0].year <= year <= DATES[1].year:
        raise dates_error(["query", "filters", "period"])
    if match["month"]:
        if not 1 <= int(match["month"]) <= 12:
            raise error(_("Invalid month."))
        return _months(dt.date(year, int(match["month"]), 1), 1)
    if match["quarter"]:
        return _months(dt.date(year, 3 * int(match["quarter"]) - 2, 1), 3)
    return [dt.date(year, 1, 1), dt.date(year, 12, 31)]


def date_range(filters, *, default=(None, None)):
    """The date range of a ``DateRangeFilter``, ``default`` without filters;
    the start or the end is ``None`` if open"""
    since, until = _period(filters.period) if filters.period else default
    for field in ["since", "until"]:
        if (day := getattr(filters, field)) and not DATES[0] <= day <= DATES[1]:
            raise dates_error(["query", "filters", field])
    since = filters.since or since
    until = filters.until or until
    if since and until and since > until:
        raise NinjaValidationError([
            {
                "loc": ["query", "filters", "until"],
                "msg": _("The end of the period must not be before its start."),
            }
        ])
    return [since, until]


def filter_date_range(queryset, filters, field):
    """Filter the queryset by the ``DateRangeFilter``'s range of ``field``"""
    since, until = date_range(filters)
    if since:
        queryset = queryset.filter(**{f"{field}__gte": since})
    if until:
        queryset = queryset.filter(**{f"{field}__lte": until})
    return queryset


class UsersFilter(Schema):
    """Short names of users or the name of a team, everyone by default"""

    user: list[str] = Field(
        default=[], description="Short names of users, can be repeated."
    )
    team: str | None = Field(
        default=None, description="Name of a team (see /api/teams/)."
    )


def user_by_short_name(short_name, *, param):
    """The user with this short name (case-insensitive) for a filter, unknown
    ones are errors instead of finding nothing"""
    if user := User.objects.by_short_name(short_name).first():
        return user
    raise NinjaValidationError([
        {
            "loc": ["query", "filters", param],
            "msg": _("Unknown user %r.") % short_name,
        }
    ])


def filter_users(filters):
    """The users of a ``UsersFilter``, ``None`` without filters"""
    if not filters.user and not filters.team:
        return None
    users = User.objects.all()
    team = None
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
        users = users.exclude(_short_name="").filter(q)
        found = {user.get_short_name().casefold() for user in users}
        if missing := [name for name in filters.user if name.casefold() not in found]:
            q = Q()
            for short_name in missing:
                q |= Q(_short_name__iexact=short_name)
            existing = {
                user.get_short_name().casefold() for user in User.objects.filter(q)
            }
            unknown = [name for name in missing if name.casefold() not in existing]
            raise NinjaValidationError([
                {
                    "loc": ["query", "filters", "user"],
                    "msg": _("Unknown users: %s") % ", ".join(unknown)
                    if unknown
                    else _("Not in the team %(team)s: %(users)s")
                    % {"team": team, "users": ", ".join(missing)},
                }
            ])
    return users


class Serialized:
    """A queryset for ninja's ``@paginate`` whose objects are serialized when
    the page is sliced, e.g. by functions which need the request"""

    def __init__(self, queryset, out, *, totals=None):
        self.queryset = queryset
        self.out = out
        self.totals = totals or {}

    def all(self):
        return self

    def count(self):
        return self.queryset.count()

    def __getitem__(self, key):
        return [self.out(obj) for obj in self.queryset[key]]


class TotalsPagination(LimitOffsetPagination):
    """Adds the totals of a ``Serialized`` queryset to the page, subclasses
    declare them in their ``Output``"""

    def paginate_queryset(self, queryset, pagination, request, **params):
        return (
            super().paginate_queryset(queryset, pagination, request, **params)
            | queryset.totals
        )


def _rounded(places):
    exponent = Decimal(1).scaleb(-places)
    return Annotated[
        Decimal,
        PlainSerializer(
            lambda value: value.quantize(exponent, rounding=ROUND_HALF_UP),
            return_type=Decimal,
        ),
    ]


# Computed values in reports, rounded like the values in the database
Amount = _rounded(2)
Hours = _rounded(1)
Days = _rounded(2)
Percentage = _rounded(1)
