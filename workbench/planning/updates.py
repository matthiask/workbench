import datetime as dt
from collections import defaultdict

from django.db.models import Q
from django.utils import timezone

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.projects.models import Project


def tryint(str):
    try:
        return int(str)
    except (TypeError, ValueError):
        return None


def updated():
    queryset = LoggedAction.objects.filter(
        created_at__gte=timezone.now() - dt.timedelta(hours=24),
        table_name__in=["planning_milestone", "planning_plannedwork"],
    ).values("user_name", "row_data__project_id")
    users = {user.id: user for user in User.objects.all()} | {None: None}

    projects = defaultdict(list)
    for row in queryset:
        pid = int(row["row_data__project_id"])
        projects[pid].append(users[audit_user_id(row["user_name"])])

    return [
        {"project": project, "updated_by": projects[project.id]}
        for project in Project.objects.open()
        .select_related("owned_by")
        .filter(Q(id__in=projects) & ~Q(type=Project.INTERNAL))
    ]


def test():  # pragma: no cover
    from pprint import pprint

    pprint(updated())
