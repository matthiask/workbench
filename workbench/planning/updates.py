import datetime as dt
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from authlib.email import render_to_mail

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.projects.models import Project


def tryint(str):
    try:
        return int(str)
    except (TypeError, ValueError):
        return None


def updated(*, duration):
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
        lambda: defaultdict(
            lambda: {
                "milestones": [],
                "deleted_work": [],
                "work": [],
            }
        )
    )

    for action in queryset:
        by = users.get(audit_user_id(action.user_name))
        project = projects.get(int(action.row_data["project_id"]))

        # Skip updates by the Wizard (migrations etc.) or where the project is gone
        if not by or not project:
            continue

        owner = users.get(project.owned_by_id)

        if action.table_name == "planning_milestone":
            if by.id != project.owned_by_id:
                updates[owner][project]["milestones"].append(
                    {
                        "action": action,
                        "by": by,
                        "pretty": _("%(by)s changed a milestone: %(title)s (%(date)s)")
                        % {
                            "by": by,
                            "title": action.new_row_data["title"],
                            "date": action.new_row_data["date"],
                        },
                    }
                )
            continue

        elif action.table_name == "planning_plannedwork":
            if action.action == "D" and by.id != project.owned_by_id:
                updates[owner][project]["deleted_work"].append(
                    {
                        "action": action,
                        "by": by,
                        "pretty": _(
                            "%(by)s deleted work managed by you: %(title)s (%(hours)sh)"
                        )
                        % {
                            "by": by,
                            "title": action.row_data["title"],
                            "hours": action.row_data["planned_hours"],
                        },
                    }
                )

            if (
                (uid := int(action.new_row_data["user_id"]))
                and (user := users.get(uid))
                and by != user
            ):
                updates[user][project]["work"].append(
                    {
                        "action": action,
                        "by": by,
                        "pretty": (
                            _("%(by)s added work for you: %(title)s (%(hours)sh)")
                            if action.action == "I"
                            else _(
                                "%(by)s changed work for you: %(title)s (%(hours)sh)"
                            )
                            if action.action == "U"
                            else _(
                                "%(by)s deleted work for you: %(title)s (%(hours)sh)"
                            )
                        )
                        % {
                            "by": by,
                            "title": action.new_row_data["title"],
                            "hours": action.new_row_data["planned_hours"],
                        },
                    }
                )

    return updates


def planning_update_mails():
    updates = updated(duration=dt.timedelta(hours=25))

    for user, user_updates in updates.items():
        if not user.is_active:
            continue
        mail = render_to_mail(
            "planning/updates_mail",
            {
                "user": user,
                "updates": sorted(user_updates.items()),
                "WORKBENCH": settings.WORKBENCH,
            },
            to=[user.email],
            cc=["workbench@feinheit.ch"],
        )
        mail.send()


def test():  # pragma: no cover
    updates = updated(duration=dt.timedelta(days=30))

    # from pprint import pprint; pprint(updates)

    for user, user_updates in updates.items():
        mail = render_to_mail(
            "planning/updates_mail",
            {
                "user": user,
                "updates": sorted(user_updates.items()),
                "WORKBENCH": settings.WORKBENCH,
            },
            to=[user.email],
            cc=["workbench@feinheit.ch"],
        )
        mail.send()
