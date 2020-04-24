from collections import defaultdict

from django.db import connections
from django.db.models import Sum

from workbench.accounts.models import User
from workbench.logbook.models import LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.formats import Z0, Z1


def green_hours(date_range, *, users=None):
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """\
WITH
service AS (
  SELECT ps.project_id, SUM(service_hours) AS hours
  FROM projects_service ps
  LEFT OUTER JOIN offers_offer o ON ps.offer_id=o.id
  WHERE ps.offer_id IS NULL OR o.status != %s
  GROUP BY ps.project_id
),
logged AS (
  SELECT project_id, SUM(hours) AS hours FROM logbook_loggedhours lh
  LEFT JOIN projects_service ps ON lh.service_id=ps.id
  GROUP BY project_id
)
SELECT logged.project_id, service.hours / logged.hours
FROM logged
LEFT JOIN service ON logged.project_id=service.project_id
WHERE service.hours / logged.hours < 1;
            """,
            [Offer.DECLINED],
        )
        green_hours_factor = defaultdict(lambda: Z0 + 1, cursor)

    within = defaultdict(lambda: defaultdict(lambda: Z1))
    project_ids = set()
    user_ids = set()

    for row in (
        LoggedHours.objects.filter(rendered_on__range=date_range)
        .order_by()
        .values("service__project", "rendered_by")
        .annotate(Sum("hours"))
    ):
        project_ids.add(row["service__project"])
        user_ids.add(row["rendered_by"])
        within[row["service__project"]][row["rendered_by"]] = row["hours__sum"]

    green = defaultdict(lambda: Z1)
    red = defaultdict(lambda: Z1)
    maintenance = defaultdict(lambda: Z1)
    internal = defaultdict(lambda: Z1)

    for project_id, type in Project.objects.filter(id__in=project_ids).values_list(
        "id", "type"
    ):
        for user_id, hours in within[project_id].items():
            if type == Project.INTERNAL:
                internal[user_id] += hours
            elif type == Project.MAINTENANCE:
                maintenance[user_id] += hours
            else:
                green[user_id] += green_hours_factor[project_id] * hours
                red[user_id] += (1 - green_hours_factor[project_id]) * hours

    def data(user_id):
        ret = {
            "green": green[user_id],
            "red": red[user_id],
            "maintenance": maintenance[user_id],
            "internal": internal[user_id],
        }
        ret["total"] = sum(ret.values())
        ret["percentage"] = (
            100 * (ret["green"] + ret["maintenance"]) / ret["total"]
            if ret["total"]
            else 0
        )
        return ret

    users = users or User.objects.filter(id__in=user_ids)
    ret = {}
    for user in users:
        ret[user] = data(user.id)
        green[0] += green[user.id]
        red[0] += red[user.id]
        maintenance[0] += maintenance[user.id]
        internal[0] += internal[user.id]
    ret[0] = data(0)
    return sorted((user, rec) for user, rec in ret.items() if rec["total"])


def green_hours_by_month():
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """\
DROP TABLE IF EXISTS green_hours_factor;
CREATE TEMPORARY TABLE green_hours_factor AS
WITH
service AS (
  SELECT ps.project_id, SUM(service_hours) AS hours
  FROM projects_service ps
  LEFT OUTER JOIN offers_offer o ON ps.offer_id=o.id
  WHERE ps.offer_id IS NULL OR o.status!=40 -- Declined
  GROUP BY ps.project_id
),
logged AS (
  SELECT project_id, SUM(hours) AS hours FROM logbook_loggedhours lh
  LEFT JOIN projects_service ps ON lh.service_id=ps.id
  GROUP BY project_id
)
SELECT
  logged.project_id,
  service.hours / logged.hours AS factor
FROM logged
LEFT JOIN service ON logged.project_id=service.project_id
WHERE service.hours / logged.hours < 1;

DROP TABLE IF EXISTS total_hours;
CREATE TEMPORARY TABLE total_hours AS
SELECT
  date_trunc('month', rendered_on) AS month,
  SUM(hours) AS total_hours
FROM logbook_loggedhours lh
LEFT JOIN projects_service ps ON lh.service_id=ps.id
GROUP BY month;

DROP TABLE IF EXISTS green_hours;
CREATE TEMPORARY TABLE green_hours AS
SELECT
  month,
  SUM(hours) AS green_hours
FROM (
  SELECT
    ps.project_id,
    date_trunc('month', rendered_on) AS month,
    hours * COALESCE(ghf.factor, 1) AS hours
  FROM logbook_loggedhours lh
  LEFT JOIN projects_service ps ON lh.service_id=ps.id
  LEFT JOIN projects_project p ON ps.project_id=p.id
  LEFT OUTER JOIN green_hours_factor ghf ON ghf.project_id=p.id
  WHERE
    p.type='order'
) subquery
GROUP BY month;

DROP TABLE IF EXISTS maintenance_hours;
CREATE TEMPORARY TABLE maintenance_hours AS
SELECT
  date_trunc('month', rendered_on) AS month,
  SUM(hours) AS maintenance_hours
FROM logbook_loggedhours lh
LEFT JOIN projects_service ps ON lh.service_id=ps.id
LEFT JOIN projects_project p ON ps.project_id=p.id
WHERE
  p.type='maintenance'
GROUP BY month;

DROP TABLE IF EXISTS internal_hours;
CREATE TEMPORARY TABLE internal_hours AS
SELECT
  date_trunc('month', rendered_on) AS month,
  SUM(hours) AS internal_hours
FROM logbook_loggedhours lh
LEFT JOIN projects_service ps ON lh.service_id=ps.id
LEFT JOIN projects_project p ON ps.project_id=p.id
WHERE
  p.type='internal'
GROUP BY month;

SELECT
  th.month,
  COALESCE(green_hours, 0),
  COALESCE(maintenance_hours, 0),
  COALESCE(internal_hours, 0),
  COALESCE(total_hours, 0)
FROM total_hours th
LEFT OUTER JOIN green_hours gh ON th.month=gh.month
LEFT OUTER JOIN maintenance_hours mh ON th.month=mh.month
LEFT OUTER JOIN internal_hours ih ON th.month=ih.month
ORDER BY th.month
        """
        )

        return [
            {
                "month": row[0].date(),
                "green": row[1],
                "maintenance": row[2],
                "internal": row[3],
                "total": row[4],
                "red": row[4] - row[1] - row[2] - row[3],
                "percentage": (100 * (row[1] + row[2]) / row[4]).quantize(Z0),
            }
            for row in cursor
        ]


def test():  # pragma: no cover
    import datetime as dt
    from pprint import pprint

    pprint(green_hours([dt.date(2019, 1, 1), dt.date(2019, 12, 31)]))
    pprint(green_hours_by_month())
