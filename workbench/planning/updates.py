import datetime as dt
from collections import defaultdict

from django.utils import timezone

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.projects.models import Project


def tryint(str):
    try:
        return int(str)
    except (TypeError, ValueError):
        return None


def updated(*, duration=dt.timedelta(hours=24)):
    queryset = LoggedAction.objects.filter(
        created_at__gte=timezone.now() - duration,
        table_name__in=["planning_milestone", "planning_plannedwork"],
    )

    users = {user.id: user for user in User.objects.all()} | {None: None}
    projects = {
        project.id: project
        for project in Project.objects.filter(
            id__in={action.row_data["project_id"] for action in queryset}
        )
    }

    updates = defaultdict(
        lambda: {
            "milestones_changed": defaultdict(list),
            "planned_work_deleted": defaultdict(list),
            "planned_work_changed": defaultdict(list),
        }
    )

    for action in queryset:
        by = audit_user_id(action.user_name)
        project = projects.get(int(action.row_data["project_id"]))

        # Skip updates by the Wizard (migrations etc.) or where the project is gone
        if not by or not project:
            continue

        if action.table_name == "planning_milestone":
            if by != project.owned_by_id:
                updates[users[project.owned_by_id]]["milestones_changed"][
                    project
                ].append(action)
            continue

        elif action.table_name == "planning_plannedwork":
            if action.action == "D" and by != project.owned_by_id:
                updates[users[project.owned_by_id]]["planned_work_deleted"][
                    project
                ].append(action)

            if (
                (uid := int(action.row_data["user_id"]))
                and (user := users.get(uid))
                and by != uid
            ):
                updates[user]["planned_work_changed"][project].append(action)

    return updates


def test():  # pragma: no cover
    from pprint import pprint

    pprint(dict(updated(duration=dt.timedelta(days=30))))
