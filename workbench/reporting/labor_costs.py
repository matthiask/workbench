from collections import defaultdict
from itertools import chain, groupby

from django.db import connections
from django.db.models import Sum

from workbench.accounts.models import User
from workbench.logbook.models import LoggedCost
from workbench.projects.models import Project
from workbench.tools.formats import Z1, Z2


LABOR_COSTS_SQL = """
select
    p.id,
    hourly_labor_costs,
    green_hours_target,
    lh.rendered_by_id,
    sum(lh.hours) as hours
from logbook_loggedhours lh
left join projects_service ps on lh.service_id=ps.id
left join projects_project p on ps.project_id=p.id
left outer join lateral (select * from awt_employment) as costs on
lh.rendered_by_id=costs.user_id
and lh.rendered_on >= costs.date_from
and lh.rendered_on <= costs.date_until
where %s
group by p.id, hourly_labor_costs, green_hours_target, lh.rendered_by_id
"""

REVENUE_SQL = """
with sq as (
    select
        p.id,
        greatest(
            coalesce(hourly_labor_costs, 0),
            coalesce(ps.effort_rate, 0)
        ) as min_effort_rate,
        sum(lh.hours) as hours
    from logbook_loggedhours lh
    left join projects_service ps on lh.service_id=ps.id
    left join projects_project p on ps.project_id=p.id
    left outer join lateral (select * from awt_employment) as costs on
    lh.rendered_by_id=costs.user_id
    and lh.rendered_on >= costs.date_from
    and lh.rendered_on <= costs.date_until
    where %s
    group by p.id, min_effort_rate
)
select id, sum(min_effort_rate * hours) from sq group by id
"""

USER_KEYS = [
    "hours",
    "hours_with_rate_undefined",
    "costs",
    "costs_with_green_hours_target",
]
PROJECT_KEYS = USER_KEYS + ["third_party_costs", "revenue"]


def _labor_costs_by_project_id(date_range, *, project=None, cost_center=None):
    projects = defaultdict(
        lambda: {
            "hours": Z1,
            "hours_with_rate_undefined": Z1,
            "costs": Z2,
            "costs_with_green_hours_target": Z2,
            "third_party_costs": Z2,
            "revenue": Z2,
            "by_user": defaultdict(
                lambda: {
                    "hours": Z1,
                    "hours_with_rate_undefined": Z1,
                    "costs": Z2,
                    "costs_with_green_hours_target": Z2,
                }
            ),
        }
    )

    logged_costs = LoggedCost.objects.order_by().filter(rendered_on__range=date_range)

    where = ["lh.rendered_on >= %s and lh.rendered_on <= %s"]
    params = date_range[:]

    if project is not None:
        where.append("p.id=%s")
        params.append(project)
        logged_costs = logged_costs.filter(service__project=project)
    if cost_center is not None:
        where.append("p.cost_center_id=%s")
        params.append(cost_center)
        logged_costs = logged_costs.filter(service__project__cost_center=cost_center)

    with connections["default"].cursor() as cursor:
        cursor.execute(LABOR_COSTS_SQL % " and ".join(where), params)

        for project_id, hlc, ght, rendered_by_id, hours in cursor:
            project = projects[project_id]
            project["hours"] += hours

            by_user = project["by_user"][rendered_by_id]
            by_user["hours"] += hours

            if hlc is None:
                project["hours_with_rate_undefined"] += hours
                by_user["hours_with_rate_undefined"] += hours

            else:
                costs = hours * hlc
                costs_with_ght = hours * hlc * 100 / ght

                project["costs"] += costs
                project["costs_with_green_hours_target"] += costs_with_ght

                by_user["costs"] += costs
                by_user["costs_with_green_hours_target"] += costs_with_ght

    with connections["default"].cursor() as cursor:
        cursor.execute(REVENUE_SQL % " and ".join(where), params)

        for project_id, revenue in cursor:
            projects[project_id]["revenue"] += revenue

    for row in (
        logged_costs.filter(third_party_costs__isnull=False)
        .values("service__project")
        .annotate(cost=Sum("third_party_costs"))
    ):
        projects[row["service__project"]]["third_party_costs"] += row["cost"]

    for row in logged_costs.values("service__project").annotate(cost=Sum("cost")):
        projects[row["service__project"]]["revenue"] += row["cost"]

    return projects


def labor_costs_by_cost_center(date_range):
    projects = _labor_costs_by_project_id(date_range)

    sorted_projects = sorted(
        [
            {"project": project, **projects[project.id]}
            for project in Project.objects.filter(
                id__in=projects.keys()
            ).select_related("cost_center", "owned_by")
        ],
        key=lambda row: (row["project"].cost_center_id or 1e100, -row["costs"]),
    )

    cost_centers = []
    for cost_center, cc_projects in groupby(
        sorted_projects, lambda row: row["project"].cost_center
    ):
        cc_projects = list(cc_projects)
        cc_row = {key: sum(row[key] for row in cc_projects) for key in PROJECT_KEYS}
        cc_row.update({"cost_center": cost_center, "projects": cc_projects})
        cost_centers.append(cc_row)

    ret = {key: sum(row[key] for row in cost_centers) for key in PROJECT_KEYS}
    ret["cost_centers"] = cost_centers
    return ret


def labor_costs_by_user(date_range, *, project=None, cost_center=None):
    projects = _labor_costs_by_project_id(
        date_range, project=project, cost_center=cost_center
    )

    users = User.objects.filter(
        id__in=set(
            chain.from_iterable(row["by_user"].keys() for row in projects.values())
        )
    )
    by_user = defaultdict(lambda: dict.fromkeys(USER_KEYS, Z2))
    overall = dict.fromkeys(PROJECT_KEYS, Z2)

    for row in projects.values():
        for key in PROJECT_KEYS:
            overall[key] += row[key]
        for key in USER_KEYS:
            for user in users:
                by_user[user][key] += row["by_user"][user.id][key]

    return {"by_user": [{"user": user, **by_user[user]} for user in users], **overall}


def test():  # pragma: no cover
    import datetime as dt
    from pprint import pprint

    pprint(labor_costs_by_cost_center([dt.date(2019, 1, 1), dt.date.today()]))
    # pprint(labor_costs_by_user([dt.date(2020, 1, 1), dt.date.today()], cost_center=1))
