import datetime as dt
import operator
from collections import defaultdict
from functools import reduce

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from authlib.email import render_to_mail

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.planning.models import Milestone, PlannedWork
from workbench.projects.models import Project
from workbench.tools.validation import monday


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


def change_object_key(action):
    return (action.table_name, int(action.row_data["id"]))


CREATE_AND_DELETE = "CREATE_AND_DELETE"
CREATE = "CREATE"
DELETE = "DELETE"
UPDATE = "UPDATE"


def change_type(actions):
    types = {a.action for a in actions}

    if {"I", "D"} <= types:
        return CREATE_AND_DELETE
    elif {"D"} <= types:
        return DELETE
    elif {"U"} == types:
        return UPDATE
    elif {"I"} <= types:
        return CREATE
    else:  # pragma: no cover
        raise NotImplementedError


def change_obj(
    type,
    actions,
    *,
    aux,
    pretty_changes=lambda x: x,
    pretty_deleted_object=lambda x: x,
):
    if type in {CREATE_AND_DELETE, DELETE}:
        return (
            {
                "type": type,
                "pretty_type": _("Deleted")
                if type == DELETE
                else _("Created and deleted"),
                "final": actions[-1].row_data,
            }
            | aux
            | {
                "object": pretty_deleted_object(actions[-1].row_data),
            }
        )

    elif type == CREATE:
        return {
            "type": type,
            "pretty_type": _("Created"),
        } | aux

    elif type == UPDATE:
        updates = reduce(
            operator.or_,
            (a.changed_fields for a in actions),
            {},
        )
        return {
            "type": type,
            "pretty_type": _("Updated"),
            "changes": pretty_changes(
                [
                    {"field": field, "old": actions[0].row_data[field], "new": updated}
                    for field, updated in updates.items()
                ]
            ),
        } | aux

    else:  # pragma: no cover
        raise NotImplementedError


def changes(*, since):
    users = {user.id: user for user in User.objects.all()}
    queryset = LoggedAction.objects.filter(
        created_at__gte=since,
        table_name__in=["planning_milestone", "planning_plannedwork"],
    )
    projects = {
        project.id: project
        for project in Project.objects.filter(
            id__in={action.row_data["project_id"] for action in queryset}
        ).select_related("owned_by")
    }

    def project_for_action(action):
        project_id = int(action.row_data["project_id"])
        if project_id not in projects:
            projects[project_id] = Project(
                id=int(project_id),
                created_at=timezone.now(),
                _code=0,
                title="<Deleted>",
                owned_by=User(id=0),
            )
        return projects[project_id]

    actions_by_object = defaultdict(list)

    for action in queryset:
        key = change_object_key(action)
        actions_by_object[key].append(action)

    milestones_by_id = {
        obj.id: obj
        for obj in Milestone.objects.filter(
            id__in=[
                key[1]
                for key in actions_by_object.keys()
                if key[0] == "planning_milestone"
            ]
        )
    }
    work_by_id = {
        obj.id: obj
        for obj in PlannedWork.objects.filter(
            id__in=[
                key[1]
                for key in actions_by_object.keys()
                if key[0] == "planning_plannedwork"
            ]
        )
    }

    milestones = defaultdict(list)
    changes = defaultdict(lambda: defaultdict(lambda: {"objects": []}))

    for key, actions in actions_by_object.items():
        type = change_type(actions)
        project = project_for_action(actions[0])
        if project.suppress_planning_update_mails:
            continue
        by = {users.get(audit_user_id(a.user_name)) for a in actions}

        # XXX Filter out changes done by users themselves and concerning only them?

        if key[0] == "planning_milestone":
            milestones[project].append(
                change_obj(
                    type,
                    actions,
                    aux={"object": milestones_by_id.get(key[1]), "by": by},
                    pretty_deleted_object=lambda x: f'{x["title"]} ({x["date"]})',
                )
            )

        elif key[0] == "planning_plannedwork":
            obj = change_obj(
                type,
                actions,
                aux={"object": work_by_id.get(key[1]), "by": by},
                pretty_deleted_object=lambda x: f'{x["title"]} ({x["planned_hours"]})',
            )
            affected = (
                {users.get(int(a.row_data["user_id"])) for a in actions}
                | {
                    users.get(int(a.changed_fields["user_id"]))
                    for a in actions
                    if a.changed_fields and "user_id" in a.changed_fields
                }
                | {project.owned_by}
            )
            for user in affected:
                if user.id:
                    changes[user][project]["objects"].append(obj)

        else:  # pragma: no cover
            raise NotImplementedError

    # Affected users are all those with planned work on the milestones' projects
    affected = {
        p: {p.owned_by} | {w.user for w in p.planned_work.all()}
        for p in Project.objects.filter(
            id__in=[p.id for p in milestones.keys()]
        ).prefetch_related("planned_work__user")
    }

    for project, affected_users in affected.items():
        for user in affected_users:
            if user.id:
                changes[user][project]["objects"].extend(milestones[project])

    for user, user_changes in changes.items():
        for project, project_changes in user_changes.items():
            project_changes["by"] = sorted(
                reduce(
                    operator.or_,
                    (obj["by"] for obj in project_changes["objects"]),
                    set(),
                )
            )

    return dict(changes)


def start_of_monday():
    return timezone.make_aware(dt.datetime.combine(monday(), dt.time.min))


def changes_mails():
    # Only on mondays
    if dt.date.today().weekday != 1:
        return

    c = changes(since=start_of_monday() - dt.timedelta(days=7))

    for user, planning_changes in sorted(c.items()):
        if not user.is_active:
            continue
        mail = render_to_mail(
            "planning/changes_mail",
            {
                "user": user,
                "changes": sorted(planning_changes.items()),
                "WORKBENCH": settings.WORKBENCH,
            },
            to=[user.email],
            cc=["workbench@feinheit.ch"],
        )
        mail.send()


def test_changes():  # pragma: no cover
    from pprint import pprint

    pprint(changes(since=start_of_monday() - dt.timedelta(days=7)))


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
