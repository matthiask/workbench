import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from workbench.accounts.models import User
from workbench.logbook.models import LoggedHours
from workbench.projects.models import Project, Service
from workbench.tools.models import Z


ONE = Decimal("1")


def green_hours(date_range):
    """
    Alternative for determining green_hours_factor:
    SELECT * FROM (
        SELECT id,
        (
            SELECT SUM(service_hours) FROM projects_service s
            WHERE p.id=s.project_id
        ) / (
            SELECT SUM(hours) FROM logbook_loggedhours lh
            LEFT JOIN projects_service s ON lh.service_id=s.id
            WHERE p.id=s.project_id
        ) AS factor
        FROM projects_project p
    ) subquery
    WHERE factor IS NOT NULL and factor < 1;
    """

    service_hours = defaultdict(
        lambda: Z,
        {
            row["project"]: row["service_hours__sum"]
            for row in Service.objects.budgeted()
            .order_by()
            .values("project")
            .annotate(Sum("service_hours"))
        },
    )
    logged_hours = defaultdict(
        lambda: Z,
        {
            row["service__project"]: row["hours__sum"]
            for row in LoggedHours.objects.order_by()
            .values("service__project")
            .annotate(Sum("hours"))
        },
    )
    green_hours_factor = {
        project_id: min(
            ONE,
            service_hours[project_id] / logged_hours[project_id]
            if logged_hours[project_id]
            else ONE,
        )
        for project_id in set(service_hours) | set(logged_hours)
    }

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
