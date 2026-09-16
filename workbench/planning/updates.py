import datetime as dt
import operator
from collections import defaultdict
from decimal import Decimal
from functools import partial, reduce
from itertools import chain

from authlib.email import render_to_mail
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.awt.models import Absence
from workbench.logbook.models import LoggedHours
from workbench.planning.models import Milestone, PlannedWork
from workbench.projects.models import Project
from workbench.tools.formats import days as days_format, local_date_format
from workbench.tools.validation import monday


# Users who logged hours on a project inside this timeframe still count as
# working on the project when determining who should hear about absences.
RECENTLY_WORKED_DAYS = 90


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
    if {"D"} <= types:
        return DELETE
    if {"U"} == types:
        return UPDATE
    if {"I"} <= types:
        return CREATE
    # pragma: no cover
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

    if type == CREATE:
        return {
            "type": type,
            "pretty_type": _("Created"),
        } | aux

    if type == UPDATE:
        updates = reduce(
            operator.or_,
            (a.changed_fields for a in actions),
            {},
        )
        return {
            "type": type,
            "pretty_type": _("Updated"),
            "changes": pretty_changes([
                {"field": field, "old": actions[0].row_data[field], "new": updated}
                for field, updated in updates.items()
            ]),
        } | aux

    # pragma: no cover
    raise NotImplementedError


def _date(value):
    return local_date_format(parse_date(value)) if value else _("<no value>")


def pretty_changes_milestone():
    def prettifier(changes):
        def _row(row):
            try:
                field = Milestone._meta.get_field(row["field"])
            except FieldDoesNotExist:
                pass
            else:
                row["pretty_field"] = field.verbose_name

            if row["field"] in {"date", "phase_starts_on"}:
                row["old"] = _date(row["old"])
                row["new"] = _date(row["new"])

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
    u = u.get_short_name() if u else x["user_id"]
    weeks = _weeks(x["weeks"])
    return f"{x['title']} ({u}, {x['planned_hours']}h, {weeks})"


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
                key[1] for key in actions_by_object if key[0] == "planning_milestone"
            ]
        )
    }
    work_by_id = {
        obj.id: obj
        for obj in PlannedWork.objects.filter(
            id__in=[
                key[1] for key in actions_by_object if key[0] == "planning_plannedwork"
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
                    pretty_deleted_object=lambda x: (
                        f"{x['title']} ({_date(x['date'])})"
                    ),
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
        for p in Project.objects.filter(id__in=[p.id for p in milestones])
    }

    for project, affected_users in affected.items():
        for user in affected_users:
            if user.id:
                changes[user][project]["objects"].extend(milestones[project])

    for user_changes in changes.values():
        for project_changes in user_changes.values():
            project_changes["by"] = sorted(
                reduce(
                    operator.or_,
                    (obj["by"] for obj in project_changes["objects"]),
                    set(),
                )
            )

    return dict(changes)


def pretty_changes_absence(*, users):
    reasons = dict(Absence.REASON_CHOICES)

    def prettifier(changes):
        def _row(row):
            try:
                field = Absence._meta.get_field(row["field"])
            except FieldDoesNotExist:
                pass
            else:
                row["pretty_field"] = field.verbose_name

            if row["field"] == "user_id":
                row["old"] = users.get(int(row["old"]), row["old"])
                row["new"] = users.get(int(row["new"]), row["new"])

            elif row["field"] in {"starts_on", "ends_on"}:
                row["old"] = _date(row["old"])
                row["new"] = _date(row["new"])

            elif row["field"] == "reason":
                row["old"] = reasons.get(row["old"], row["old"])
                row["new"] = reasons.get(row["new"], row["new"])

            return row

        return [
            _row(row)
            for row in changes
            # Both fields are derived from the reason.
            if row["field"] not in {"is_vacation", "is_working_time"}
        ]

    return prettifier


def pretty_absence(x, *, users):
    user = users.get(int(x["user_id"]))
    user = user.get_short_name() if user else x["user_id"]
    starts_on, ends_on = parse_date(x["starts_on"]), parse_date(x["ends_on"] or "")
    period = (
        f"{local_date_format(starts_on)} - {local_date_format(ends_on)}"
        if ends_on and ends_on != starts_on
        else local_date_format(starts_on)
    )
    reason = dict(Absence.REASON_CHOICES).get(x["reason"], x["reason"])
    absence = f"{user}: {reason}, {period} ({days_format(Decimal(x['days']))})"
    return f"{absence} {x['description']}" if x["description"] else absence


def absence_touches_future(actions, *, today):
    """Absences which are completely in the past do not concern the planning"""
    return any(
        (end := data["ends_on"] or data["starts_on"]) and parse_date(end) >= today
        for action in actions
        for data in (action.row_data, action.new_row_data)
    )


def project_involvement(*, today):
    """
    Return projects and the users involved in them

    Involved means either being planned on the project now or in the future, or
    having worked on the project recently. Project owners are involved in their
    own projects as soon as anyone else is.
    """
    projects = {
        project.id: project
        for project in Project.objects
        .open()
        .filter(suppress_planning_update_mails=False)
        .select_related("owned_by")
    }
    planned = (
        PlannedWork.objects
        .filter(project__in=projects.keys())
        .annotate(
            max_weeks=RawSQL("(select max(elements) from unnest(weeks) elements)", ())
        )
        .filter(max_weeks__gte=today)
        .values_list("project_id", "user_id")
    )
    worked = (
        LoggedHours.objects
        .filter(
            service__project__in=projects.keys(),
            rendered_on__gte=today - dt.timedelta(days=RECENTLY_WORKED_DAYS),
        )
        .values_list("service__project_id", "rendered_by_id")
        .distinct()
    )

    involved = defaultdict(set)
    for project_id, user_id in chain(planned, worked):
        involved[project_id].add(user_id)
    # Owners are only involved in projects where something is happening --
    # otherwise long-forgotten open projects would pad everyone's mail.
    for project_id, user_ids in involved.items():
        user_ids.add(projects[project_id].owned_by_id)
    return projects, involved


def absence_changes(*, since):
    """
    Absence changes of people one shares projects with

    Everyone involved in a project (see :func:`project_involvement`) hears about
    the absences of everyone else involved in the same project, the project
    owner included -- in both directions.
    """
    today = dt.date.today()
    users = {user.id: user for user in User.objects.all()}
    actions_by_object = defaultdict(list)

    for action in LoggedAction.objects.filter(
        created_at__gte=since, table_name="awt_absence"
    ):
        actions_by_object[change_object_key(action)].append(action)

    if not actions_by_object:
        return {}

    projects, involved = project_involvement(today=today)
    projects_of_user = defaultdict(list)
    for project_id, user_ids in involved.items():
        for user_id in user_ids:
            projects_of_user[user_id].append(projects[project_id])

    changes = defaultdict(list)

    for actions in actions_by_object.values():
        final = actions[-1].new_row_data
        # Working time corrections aren't absences anyone has to plan around.
        if final["reason"] == Absence.CORRECTION:
            continue
        if not absence_touches_future(actions, today=today):
            continue

        obj = change_obj(
            change_type(actions),
            actions,
            aux={
                "object": pretty_absence(final, users=users),
                "by": sorted(
                    filter(
                        None, (users.get(audit_user_id(a.user_name)) for a in actions)
                    )
                ),
            },
            pretty_changes=pretty_changes_absence(users=users),
            pretty_deleted_object=partial(pretty_absence, users=users),
        )

        # The absence may have been moved from one user to the other.
        absent = {
            int(data["user_id"])
            for action in actions
            for data in (action.row_data, action.new_row_data)
        }
        recipients = defaultdict(set)
        for user_id in absent:
            for project in projects_of_user[user_id]:
                for recipient_id in involved[project.id]:
                    if recipient := users.get(recipient_id):
                        recipients[recipient].add(project)

        for recipient, recipient_projects in recipients.items():
            changes[recipient].append(obj | {"projects": sorted(recipient_projects)})

    return {
        user: sorted(user_changes, key=lambda obj: obj["object"])
        for user, user_changes in changes.items()
    }


def start_of_monday():
    return timezone.make_aware(dt.datetime.combine(monday(), dt.time.min))


def changes_mails():
    # Only on mondays
    if dt.date.today().weekday() != 0:
        return

    since = start_of_monday() - dt.timedelta(days=7)
    c = changes(since=since)
    a = absence_changes(since=since)

    for user in sorted(set(c) | set(a)):
        if not user.is_active:
            continue
        mail = render_to_mail(
            "planning/changes_mail",
            {
                "user": user,
                "changes": sorted(c.get(user, {}).items()),
                "absences": a.get(user, []),
                "WORKBENCH": settings.WORKBENCH,
            },
            to=[user.email],
            reply_to=[user.email],
        )
        mail.send()


def test():  # pragma: no cover
    from pprint import pprint

    since = start_of_monday() - dt.timedelta(days=7)
    pprint(changes(since=since))
    pprint(absence_changes(since=since))
