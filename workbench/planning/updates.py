import datetime as dt
import operator
from collections import defaultdict
from functools import partial, reduce

from authlib.email import render_to_mail
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.planning.models import Milestone, PlannedWork
from workbench.projects.models import Project
from workbench.tools.formats import local_date_format
from workbench.tools.validation import monday


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


def pretty_changes_milestone():
    def prettifier(changes):
        def _row(row):
            try:
                field = Milestone._meta.get_field(row["field"])
            except FieldDoesNotExist:
                pass
            else:
                row["pretty_field"] = field.verbose_name
            return row

        return [_row(row) for row in changes]

    return prettifier


def _weeks(weeks):
    w = weeks[1:-1].split(",")
    start, end = parse_date(w[0]), parse_date(w[-1]) + dt.timedelta(days=6)
    return f"{local_date_format(start)} - {local_date_format(end)}"


def pretty_changes_work(*, users, milestones):
    def prettifier(changes):
        def _row(row):
            try:
                field = PlannedWork._meta.get_field(row["field"])
            except FieldDoesNotExist:
                pass
            else:
                row["pretty_field"] = field.verbose_name

            if row["field"] == "user_id":
                row["old"] = users.get(int(row["old"]), row["old"])
                row["new"] = users.get(int(row["new"]), row["new"])

            elif row["field"] == "weeks":
                row["old"] = _weeks(row["old"])
                row["new"] = _weeks(row["new"])

            elif row["field"] == "milestone_id":
                if row["old"]:
                    row["old"] = milestones.get(int(row["old"]), row["old"])
                else:
                    row["old"] = _("<no value>")
                if row["new"]:
                    row["new"] = milestones.get(int(row["new"]), row["new"])
                else:
                    row["new"] = _("<no value>")

            return row

        return [
            _row(row)
            for row in changes
            if row["field"] not in {"notes", "service_type_id"}
        ]

    return prettifier


def pretty_deleted_object_work(x, *, users):
    u = users.get(int(x["user_id"]))
    if u:
        u = u.get_short_name()
    else:
        u = x["user_id"]
    weeks = _weeks(x["weeks"])
    return f'{x["title"]} ({u}, {x["planned_hours"]}h, {weeks})'


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
    project_milestones = {
        m.id: m for m in Milestone.objects.filter(project__in=projects.keys())
    }

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
                    pretty_changes=pretty_changes_milestone(),
                    pretty_deleted_object=lambda x: f'{x["title"]} ({x["date"]})',
                )
            )

        elif key[0] == "planning_plannedwork":
            obj = change_obj(
                type,
                actions,
                aux={"object": work_by_id.get(key[1]), "by": by},
                pretty_changes=pretty_changes_work(
                    users=users, milestones=project_milestones
                ),
                pretty_deleted_object=partial(pretty_deleted_object_work, users=users),
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
        p: {p.owned_by}
        | {
            w.user
            for w in p.planned_work.annotate(
                max_weeks=RawSQL(
                    "(select max(elements) from unnest(weeks) elements)", ()
                )
            ).filter(max_weeks__gte=dt.date.today())
        }
        for p in Project.objects.filter(id__in=[p.id for p in milestones.keys()])
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
    if dt.date.today().weekday() != 0:
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


def test():  # pragma: no cover
    from pprint import pprint

    pprint(changes(since=start_of_monday() - dt.timedelta(days=7)))
