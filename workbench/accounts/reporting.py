from django.db import connections
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.tools.validation import in_days


def query(sql, params):
    with connections["default"].cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor)


def logged_hours(user):
    stats = {}
    stats["hours_per_week"] = [
        {"week": week, "hours": hours}
        for week, hours in query(
            """
SELECT
    date_trunc('week', rendered_on) AS week,
    SUM(hours)
FROM logbook_loggedhours
WHERE rendered_by_id=%s AND rendered_on>=%s
GROUP BY week
ORDER BY week
""",
            [user.id, in_days(-365)],
        )
    ]

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
SELECT
    (extract(isodow from rendered_on)::integer) as dow,
    SUM(hours)
FROM logbook_loggedhours
WHERE rendered_by_id=%s AND rendered_on>=%s
GROUP BY dow
ORDER BY dow
            """,
            [user.id, in_days(-365)],
        )
    ]

    stats["created_hours_per_weekday"] = [
        {"dow": int(dow), "name": dows[int(dow)], "hours": hours}
        for dow, hours in query(
            """
SELECT
    (extract(isodow from created_at)::integer) as dow,
    SUM(hours)
FROM logbook_loggedhours
WHERE rendered_by_id=%s AND rendered_on>=%s
GROUP BY dow
ORDER BY dow
            """,
            [user.id, in_days(-365)],
        )
    ]

    return stats


def test():  # pragma: no cover
    from pprint import pprint

    # today = dt.date.today()
    # date_range = [today - dt.timedelta(days=56), today]
    # pprint(mean_logging_delay(date_range))
    # pprint(logged_hours_stats(date_range))
    # pprint(insufficient_breaks(date_range))
    # pprint(logbook_stats(date_range))

    u = User.objects.get(pk=1)
    pprint(logged_hours(u))
