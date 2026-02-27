import datetime as dt
from collections import defaultdict
from itertools import starmap
from types import SimpleNamespace

from django.db.models import Sum
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.reporting import employment_percentages
from workbench.contacts.models import Organization
from workbench.logbook.models import LoggedHours
from workbench.projects.models import InternalType, InternalTypeUser, Project
from workbench.tools.formats import Z1, Z2
from workbench.tools.forms import querystring


def hours_per_customer(date_range, *, users=None):
    hours = defaultdict(lambda: defaultdict(lambda: Z1))
    user_hours = defaultdict(lambda: Z1)
    seen_organizations = set()
    seen_users = set()

    queryset = LoggedHours.objects.order_by().filter(rendered_on__range=date_range)
    if users:
        queryset = queryset.filter(rendered_by__in=users)

    for row in queryset.values("rendered_by", "service__project__customer").annotate(
        Sum("hours")
    ):
        hours[row["service__project__customer"]][row["rendered_by"]] = row["hours__sum"]
        user_hours[row["rendered_by"]] += row["hours__sum"]
        seen_organizations.add(row["service__project__customer"])
        seen_users.add(row["rendered_by"])

    user_list = User.objects.filter(id__in=seen_users)

    organizations = [
        {
            "organization": org,
            "user_hours": [(user, hours[org.id][user.id]) for user in user_list],
            "total_hours": sum(hours[org.id].values(), Z1),
        }
        for org in Organization.objects.filter(id__in=seen_organizations)
    ]

    return {
        "organizations": sorted(
            organizations, key=lambda row: row["total_hours"], reverse=True
        ),
        "users": user_list,
        "user_hours": [(user, user_hours[user.id]) for user in user_list],
        "total_hours": sum(user_hours.values(), Z1),
    }


def highlight_external(row):
    if row["reached"] >= row["expected"]:
        return row | {"highlight": "text-success"}
    if row["reached"] < row["expected"] - 10:
        return row | {"highlight": "text-warning"}
    return row


def highlight_internal(row, *, is_last):
    if is_last and row["reached"] > row["expected"] + 5:
        return row | {"highlight": "text-warning"}
    if is_last:
        return row

    if row["reached"] > row["expected"]:
        return row | {"highlight": "text-info"}
    if row["reached"] < row["expected"] / 2:
        return row | {"highlight": "text-warning"}

    return row


def hours_per_type(date_range, *, users=None):
    hours = defaultdict(lambda: defaultdict(lambda: Z1))

    queryset = LoggedHours.objects.order_by().filter(rendered_on__range=date_range)

    user_dict = {u.id: u for u in User.objects.all()}

    user_internal_types = defaultdict(dict)
    for m2m in InternalTypeUser.objects.select_related("internal_type"):
        user_internal_types[user_dict[m2m.user_id]][m2m.internal_type] = m2m

    if users:
        queryset = queryset.filter(rendered_by__in=users)
    for row in queryset.values(
        "rendered_by", "service__project__type", "service__project__internal_type"
    ).annotate(Sum("hours")):
        u = user_dict[row["rendered_by"]]
        if row["service__project__type"] == Project.INTERNAL:
            hours[u][row["service__project__internal_type"]] += row["hours__sum"]
        else:
            hours[u][0] += row["hours__sum"]

    external_type = SimpleNamespace(id=0, name=_("External"), description="")
    internal_types = list(InternalType.objects.all())

    def _logbook_url(**kwargs):
        return "{}{}".format(
            LoggedHours.urls["list"],
            querystring(
                date_from=date_range[0].isoformat(),
                date_until=date_range[1].isoformat(),
                **kwargs,
            ),
        )

    def _user(u, row):
        uit = user_internal_types[u]

        internal_percentages = [
            uit[type].percentage if type in uit else 0 for type in internal_types
        ]
        profitable_percentage = 100 - sum(internal_percentages)
        total = sum(row.values(), 0)
        hours_per_type = [
            highlight_external({
                "id": 0,
                "type": external_type,
                "hours": row[0],
                "expected": profitable_percentage,
                "reached": 100 * row[0] / total,
                "url": _logbook_url(rendered_by=u.id, internal_type=-1),
            })
        ] + [
            highlight_internal(
                {
                    "id": type.id,
                    "type": type.name,
                    "hours": row[type.id],
                    "expected": uit[type].percentage if type in uit else 0,
                    "reached": 100 * row[type.id] / total,
                    "url": _logbook_url(rendered_by=u.id, internal_type=type.id),
                },
                is_last=type == internal_types[-1],
            )
            for type in internal_types
        ]
        return {
            "user": u,
            "hours_per_type": hours_per_type,
            "internal": total - row[0],
            "external": row[0],
            "total_hours_per_type": {row["id"]: row["hours"] for row in hours_per_type},
            "total": total,
            "url": _logbook_url(rendered_by=u.id),
        }

    users = list(starmap(_user, sorted(hours.items())))

    return {
        "types": [external_type, *internal_types],
        "users": users,
        "total": {
            "internal": sum((row["internal"] for row in users), Z1),
            "external": sum((row["external"] for row in users), Z1),
            "total": sum((row["total"] for row in users), Z1),
        },
        "overall": [
            {
                "hours": sum((row["total_hours_per_type"][0] for row in users), Z1),
                "url": _logbook_url(internal_type=-1),
            }
        ]
        + [
            {
                "hours": sum(
                    (row["total_hours_per_type"][type.id] for row in users), Z1
                ),
                "url": _logbook_url(internal_type=type.id),
            }
            for type in internal_types
        ],
        "logbook_url": "{}{}".format(
            LoggedHours.urls["list"],
            querystring(
                date_from=date_range[0].isoformat(),
                date_until=date_range[1].isoformat(),
            ),
        ),
    }


def hours_per_type_distribution(year):
    user_internal_types = defaultdict(dict)
    for m2m in InternalTypeUser.objects.select_related("internal_type"):
        user_internal_types[m2m.user_id][m2m.internal_type] = m2m

    ep = employment_percentages(until_year=year)

    months = [dt.date(year, month, 1) for month in range(1, 13)]

    fte_per_field = defaultdict(lambda: Z2)
    fte_per_field_and_type = defaultdict(lambda: defaultdict(lambda: Z2))

    for user, user_ep in ep.items():
        for month in months:
            if percentage := user_ep[month]:
                fte_per_field[user.specialist_field] += percentage / 100 / 12

    for user in User.objects.select_related("specialist_field"):
        field = fte_per_field_and_type[user.specialist_field]

        for type, typeuser in user_internal_types[user.id].items():
            for month in months:
                field[type] += ep[user][month] / 12 * typeuser.percentage / 10000

    external_type = SimpleNamespace(id=0, name=_("External"), description="")
    internal_types = list(InternalType.objects.all())

    table = [
        [
            "Fachbereich",
            external_type.name,
            *(type.name for type in internal_types),
            "Total",
        ]
    ]

    overall = sum(fte_per_field.values()) / 100

    internal_total_per_type = defaultdict(lambda: Z2)
    for field, types in sorted(fte_per_field_and_type.items()):
        if not fte_per_field[field]:
            continue

        internal = [types[type] for type in internal_types]
        table.append([
            field.name if field else "??",
            ((fte_per_field[field] - sum(internal)) / overall).quantize(Z2),
            *((number / overall).quantize(Z2) for number in internal),
            (fte_per_field[field] / overall).quantize(Z2),
        ])

        for type, total in types.items():
            internal_total_per_type[type] += total

    table.append([
        "Gesamtes Team",
        (
            (sum(fte_per_field.values()) - sum(internal_total_per_type.values()))
            / overall
        ).quantize(Z2),
        *(
            (internal_total_per_type[type] / overall).quantize(Z2)
            for type in internal_types
        ),
        (sum(fte_per_field.values()) / overall).quantize(Z2),
    ])

    # return fte_per_field, fte_per_field_and_type
    return table


def test():  # pragma: no cover
    # pprint(hours_per_type([dt.date(2022, 1, 1), dt.date(2022, 12, 31)]))

    from pprint import pprint

    pprint(hours_per_type_distribution(2025))
