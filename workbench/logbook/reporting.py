import datetime as dt

from django.db import connections
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User


class LoggingDelay:
    IMMEDIATE = _("Immediate"), "success"
    SAME_DAY = _("Same day"), "light"
    NEXT_DAY = _("Next day"), "caveat"
    LATE = _("Late"), "danger"


def classify_logging_delay(delay):
    explanation = _("Average logging time is %.1f hours after noon.") % delay

    if delay < 3:
        return _("Immediate"), "success", explanation
    elif delay < 8:
        return _("Same day"), "light", explanation
    elif delay < 30:
        return _("Next day"), "caveat", explanation

    explanation = _("Average logging delay is %.1f days.") % (delay / 24)
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
SELECT user_id, ceil(extract(epoch from delay) / 3600)
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


def logbook_stats(date_range):
    mld = mean_logging_delay(date_range)
    lhs = logged_hours_stats(date_range)

    users = User.objects.filter(id__in=mld.keys() | lhs.keys())

    return [
        {
            "user": user,
            "mean_logging_delay": mld[user.id],
            "logged_hours_stats": lhs[user.id],
        }
        for user in users
    ]


def test():  # pragma: no cover
    from pprint import pprint

    today = dt.date.today()
    date_range = [today - dt.timedelta(days=56), today]

    # pprint(mean_logging_delay(date_range))
    # pprint(logged_hours_stats(date_range))

    pprint(logbook_stats(date_range))
