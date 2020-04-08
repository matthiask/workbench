import datetime as dt
from collections import defaultdict

from django.db import connections
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.tools.validation import in_days, monday


def query(sql, params):
    with connections["default"].cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor)


def logged_hours(user):
    stats = {}

    from_ = monday(in_days(-365))
    hours_per_week = {}
    for week, type, hours in query(
        """
WITH sq AS (
    SELECT
        date_trunc('week', rendered_on) AS week,
        project.type AS type,
        SUM(hours) AS hours
    FROM logbook_loggedhours hours
    LEFT JOIN projects_service service ON hours.service_id=service.id
    LEFT JOIN projects_project project ON service.project_id=project.id
    WHERE rendered_by_id=%s AND rendered_on>=%s
    GROUP BY week, project.type
)
SELECT series.week, sq.type, COALESCE(sq.hours, 0)
FROM generate_series(%s, %s, '7 days') AS series(week)
LEFT OUTER JOIN sq ON series.week=sq.week
ORDER BY series.week
""",
        [user.id, from_, from_, monday() + dt.timedelta(days=6)],
    ):
        if week in hours_per_week:
            hours_per_week[week]["hours"] += hours
            hours_per_week[week]["by_type"][type] = hours
        else:
            hours_per_week[week] = {
                "week": week,
                "hours": hours,
                "by_type": {type: hours},
            }

    stats["hours_per_week"] = [row[1] for row in sorted(hours_per_week.items())]

    hours_per_customer = defaultdict(dict)
    total_hours_per_customer = defaultdict(int)

    for week, customer, hours in query(
        """
WITH sq AS (
    SELECT
        date_trunc('week', rendered_on) AS week,
        customer.name AS customer,
        SUM(hours) AS hours
    FROM logbook_loggedhours hours
    LEFT JOIN projects_service service ON hours.service_id=service.id
    LEFT JOIN projects_project project ON service.project_id=project.id
    LEFT JOIN contacts_organization customer ON project.customer_id=customer.id
    WHERE rendered_by_id=%s AND rendered_on>=%s
    GROUP BY week, customer.name
)
SELECT series.week, COALESCE(sq.customer, ''), COALESCE(sq.hours, 0)
FROM generate_series(%s, %s, '7 days') AS series(week)
LEFT OUTER JOIN sq ON series.week=sq.week
ORDER BY series.week
        """,
        [user.id, from_, from_, monday() + dt.timedelta(days=6)],
    ):
        hours_per_customer[week][customer] = hours
        total_hours_per_customer[customer] += hours

    customers = [
        row[0]
        for row in sorted(
            total_hours_per_customer.items(), key=lambda row: row[1], reverse=True
        )
    ][:10]

    weeks = sorted(hours_per_customer.keys())
    stats["hours_per_customer"] = {
        "weeks": weeks,
        "by_customer": [
            {
                "name": customer.split("\n")[0],
                "hours": [hours_per_customer[week].get(customer, 0) for week in weeks],
            }
            for customer in customers
        ],
    }
    customers = set(customers)
    stats["hours_per_customer"]["by_customer"].append(
        {
            "name": _("Everyone else"),
            "hours": [
                sum(
                    (
                        hours
                        for customer, hours in hours_per_customer[week].items()
                        if customer not in customers
                    ),
                    0,
                )
                for week in weeks
            ],
        }
    )

    dows = [
        None,
        _("Monday"),
        _("Tuesday"),
        _("Wednesday"),
        _("Thursday"),
        _("Friday"),
        _("Saturday"),
        _("Sunday"),
    ]

    stats["rendered_hours_per_weekday"] = [
        {"dow": int(dow), "name": dows[int(dow)], "hours": hours}
        for dow, hours in query(
            """
WITH sq AS (
    SELECT
        (extract(isodow from rendered_on)::integer) as dow,
        SUM(hours) AS hours
    FROM logbook_loggedhours
    WHERE rendered_by_id=%s AND rendered_on>=%s
    GROUP BY dow
    ORDER BY dow
)
SELECT series.dow, COALESCE(sq.hours, 0)
FROM generate_series(1, 7) AS series(dow)
LEFT OUTER JOIN sq ON series.dow=sq.dow
ORDER BY series.dow
            """,
            [user.id, in_days(-365)],
        )
    ]

    stats["created_hours_per_weekday"] = [
        {"dow": int(dow), "name": dows[int(dow)], "hours": hours}
        for dow, hours in query(
            """
WITH sq AS (
    SELECT
        (extract(isodow from timezone('CET', created_at))::integer) as dow,
        SUM(hours) AS hours
    FROM logbook_loggedhours
    WHERE rendered_by_id=%s AND rendered_on>=%s
    GROUP BY dow
    ORDER BY dow
)
SELECT series.dow, COALESCE(sq.hours, 0)
FROM generate_series(1, 7) AS series(dow)
LEFT OUTER JOIN sq ON series.dow=sq.dow
ORDER BY series.dow
            """,
            [user.id, in_days(-365)],
        )
    ]

    return stats


def test():  # pragma: no cover
    from pprint import pprint

    u = User.objects.get(pk=1)
    pprint(logged_hours(u))
