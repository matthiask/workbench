import datetime as dt
from collections import defaultdict

from django.db import connections

from workbench.projects.models import Project
from workbench.tools.models import Z


SQL = """
select
    ps.project_id,
    hourly_labor_costs,
    green_hours_target,
    sum(lh.hours) as hours
from logbook_loggedhours lh
left join projects_service ps on lh.service_id=ps.id
left outer join lateral (select * from awt_employment) as costs on
lh.rendered_by_id=costs.user_id
and lh.rendered_on >= costs.date_from
and lh.rendered_on <= costs.date_until
%s
group by ps.project_id, hourly_labor_costs, green_hours_target
"""


def labor_costs(date_range):
    projects = defaultdict(
        lambda: {
            "hours": Z,
            "hours_with_rate_undefined": Z,
            "costs": Z,
            "costs_with_green_hours_target": Z,
        }
    )

    with connections["default"].cursor() as cursor:
        cursor.execute(
            SQL % "where lh.rendered_on >= %s and lh.rendered_on <= %s", date_range
        )

        for project_id, hlc, ght, hours in cursor:
            project = projects[project_id]
            project["hours"] += hours
            if hlc is None:
                project["hours_with_rate_undefined"] += hours
            else:
                project["costs"] += hours * hlc
                project["costs_with_green_hours_target"] += hours * hlc * 100 / ght

    return [
        {"project": project, **projects[project.id]}
        for project in Project.objects.filter(id__in=projects.keys()).select_related(
            "owned_by"
        )
    ]


def test():
    from pprint import pprint

    pprint(labor_costs([dt.date(2019, 1, 1), dt.date(2019, 12, 31)]))
