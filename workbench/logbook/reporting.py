import datetime as dt

from django.db import connections
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.formats import Z1, days, hours


def classify_logging_delay(delay):
    explanation = _("Average logging time is %s after noon.") % hours(delay)

    if delay < 3:
        return _("Promptly"), "success", explanation
    elif delay < 8:
        return _("Same day"), "light", explanation
    elif delay < 30:
        return _("Next day"), "caveat", explanation

    explanation = _("Average logging delay is %s.") % days(delay / 24)
    return _("Late"), "danger", explanation


def mean_logging_delay(date_range):
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """
WITH sq as (
    SELECT
        rendered_by_id AS user_id,
        AVG(created_at - (rendered_on + interval '12 hours')) AS delay
    FROM logbook_loggedhours
    WHERE rendered_on BETWEEN %s AND %s
    GROUP BY user_id
)
SELECT user_id, cast(extract(epoch from delay) as numeric) / 3600
FROM sq
            """,
            date_range,
        )

        return {
            user_id: {"delay": delay, "classification": classify_logging_delay(delay)}
            for user_id, delay in cursor
        }


def logged_hours_stats(date_range):
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """
SELECT rendered_by_id, COUNT(hours), SUM(hours), AVG(hours)
FROM logbook_loggedhours
WHERE rendered_on BETWEEN %s AND %s
GROUP BY rendered_by_id
            """,
            date_range,
        )

        return {
            user_id: {"count": count, "sum": sum, "avg": avg}
            for user_id, count, sum, avg in cursor
        }


def insufficient_breaks(date_range):
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """
with breaks as (
    select
        user_id,
        date_trunc('day', starts_at) as day,
        sum(extract(epoch from (ends_at - starts_at))) as break_seconds
    from logbook_break
    where date_trunc('day', starts_at) between %s and %s
    group by user_id, day
),
logged_hours as (
    select
        rendered_by_id as user_id,
        rendered_on as day,
        sum(hours) as hours
    from logbook_loggedhours
    where rendered_on between %s and %s
    group by user_id, day
),
combined as (
    select
        logged_hours.user_id,
        logged_hours.day,
        hours,
        coalesce(break_seconds, 0) as break_seconds
    from logged_hours
    left join breaks
    on
        breaks.user_id=logged_hours.user_id
        and breaks.day=logged_hours.day
),
insufficient_breaks as (
    select * from combined
    where
        hours >= 9 and break_seconds < 3600
        or hours >= 7 and break_seconds < 1800
        or hours >= 5.5 and break_seconds < 900
)
select
    user_id,
    count(*),
    (
        select count(*)
        from insufficient_breaks
        where insufficient_breaks.user_id=logged_hours.user_id
    )
from logged_hours
group by user_id
            """,
            [*date_range, *date_range],
        )

        return {user_id: {"days": days, "of": of} for user_id, of, days in cursor}


def logbook_stats(date_range):
    mld = mean_logging_delay(date_range)
    lhs = logged_hours_stats(date_range)
    ib = insufficient_breaks(date_range)

    users = [
        {
            "user": user,
            "mean_logging_delay": mld[user.id],
            "logged_hours_stats": lhs[user.id],
            "insufficient_breaks": ib[user.id],
        }
        for user in User.objects.filter(id__in=mld.keys() | lhs.keys())
    ]

    lhs_count = sum((user["logged_hours_stats"]["count"] for user in users), 0)
    lhs_sum = sum((user["logged_hours_stats"]["sum"] for user in users), Z1)

    return {
        "users": users,
        "logged_hours_stats": {
            "count": lhs_count,
            "sum": lhs_sum,
            "avg": lhs_sum / lhs_count if lhs_count else None,
        },
        "insufficient_breaks": {
            "days": sum((user["insufficient_breaks"]["days"] for user in users), 0),
            "of": sum((user["insufficient_breaks"]["of"] for user in users), 0),
        },
    }


def test():  # pragma: no cover
    from pprint import pprint

    today = dt.date.today()
    date_range = [today - dt.timedelta(days=56), today]

    # pprint(mean_logging_delay(date_range))
    # pprint(logged_hours_stats(date_range))
    # pprint(insufficient_breaks(date_range))
    pprint(logbook_stats(date_range))
