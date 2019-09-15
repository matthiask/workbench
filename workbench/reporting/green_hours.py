import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db import connections
from django.db.models import Sum

from workbench.accounts.models import User
from workbench.logbook.models import LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.models import Z


ONE = Decimal("1")


def green_hours(date_range):
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
            [Offer.REJECTED],
        )
        green_hours_factor = defaultdict(lambda: ONE, cursor)

    within = defaultdict(lambda: defaultdict(lambda: Z))
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

    green = defaultdict(lambda: Z)
    red = defaultdict(lambda: Z)
    maintenance = defaultdict(lambda: Z)
    internal = defaultdict(lambda: Z)

    for project_id, type in Project.objects.filter(id__in=project_ids).values_list(
        "id", "type"
    ):
        for user_id, hours in within[project_id].items():
            if type == Project.INTERNAL:
                internal[0] += hours
                internal[user_id] += hours
            elif type == Project.MAINTENANCE:
                maintenance[0] += hours
                maintenance[user_id] += hours
            else:
                green[0] += green_hours_factor[project_id] * hours
                green[user_id] += green_hours_factor[project_id] * hours
                red[0] += (ONE - green_hours_factor[project_id]) * hours
                red[user_id] += (ONE - green_hours_factor[project_id]) * hours

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

    ret = {0: data(0)}
    for user in User.objects.filter(id__in=user_ids):
        ret[user] = data(user.id)
    return sorted(ret.items())


def test():  # pragma: no cover
    from pprint import pprint

    pprint(green_hours([dt.date(2019, 1, 1), dt.date(2019, 12, 31)]))
