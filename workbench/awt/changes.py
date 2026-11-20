"""
Changes of others affecting someone's annual working time: logged hours and
absences entered, changed or deleted by someone else than the person they
belong to. Personnel administration gets a weekly mail listing them, the
forms warn beforehand.
"""

import datetime as dt
from decimal import Decimal

from authlib.email import render_to_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy, override

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.awt.models import Absence
from workbench.logbook.models import LoggedHours
from workbench.projects.models import Service
from workbench.tools.formats import days, hours, local_date_format
from workbench.tools.validation import monday


#: Changes of an entry by the same person this close to each other are one
COALESCE = dt.timedelta(hours=1)

#: Fields of absences affecting the annual working time besides the dates
ABSENCE_FIELDS = ["user_id", "days", "reason", "is_vacation", "is_working_time"]


def is_reported_move(old_day, new_day):
    """
    The annual working time sums up months, moving hours within a month
    doesn't change it. Moving them within a week is a correction while
    logging (the logbook locks weeks), even across the end of a month.
    """
    return old_day.replace(day=1) != new_day.replace(day=1) and monday(
        old_day
    ) != monday(new_day)


def is_reported(instance):
    """Working time corrections are entered by personnel administration"""
    return not isinstance(instance, Absence) or instance.reason != Absence.CORRECTION


HOURS_WARNING = gettext_lazy(
    "These are someone else's hours. Logging, changing and deleting them is"
    " reported to personnel administration weekly."
)
ABSENCE_WARNING = gettext_lazy(
    "This is someone else's absence. Entering, changing and deleting it is"
    " reported to personnel administration weekly."
)


def personnel_administration():
    """The recipients of ``changes_by_others_mails()``"""
    return [
        user
        for user in User.objects.active()
        if user.features[FEATURES.PERSONNEL_ADMINISTRATION]
    ]


def _date(value):
    return dt.date.fromisoformat(value) if value else None


def _change(old, new, fmt=str):
    return f"{fmt(old)} → {fmt(new)}"


def _hours_changes(old, new, users):
    """What an update of logged hours changed of the annual working time"""
    changes = []
    if Decimal(old["hours"]) != Decimal(new["hours"]):
        changes.append(_change(Decimal(old["hours"]), Decimal(new["hours"]), hours))
    if old["rendered_by_id"] != new["rendered_by_id"]:
        changes.append(
            _change(
                users.get(int(old["rendered_by_id"])),
                users.get(int(new["rendered_by_id"])),
            )
        )
    old_day, new_day = _date(old["rendered_on"]), _date(new["rendered_on"])
    if is_reported_move(old_day, new_day):
        changes.append(_change(old_day, new_day, local_date_format))
    return changes


def _absence_changes(old, new, users):
    """What an update of an absence changed of the annual working time"""
    if old == new:
        return []
    changes = []
    if Decimal(old["days"]) != Decimal(new["days"]):
        changes.append(_change(Decimal(old["days"]), Decimal(new["days"]), days))
    if old["user_id"] != new["user_id"]:
        changes.append(
            _change(users.get(int(old["user_id"])), users.get(int(new["user_id"])))
        )
    if old["reason"] != new["reason"]:
        reasons = dict(Absence.REASON_CHOICES)
        changes.append(_change(reasons[old["reason"]], reasons[new["reason"]]))
    for field in ["is_vacation", "is_working_time"]:
        if old[field] != new[field]:
            changes.append(
                _change(
                    old[field] == "t",
                    new[field] == "t",
                    lambda value, field=field: "{}: {}".format(
                        Absence._meta.get_field(field).verbose_name,
                        _("yes") if value else _("no"),
                    ),
                )
            )
    for field in ["starts_on", "ends_on"]:
        old_day = _date(old[field] or old["starts_on"])
        new_day = _date(new[field] or new["starts_on"])
        if is_reported_move(old_day, new_day):
            changes.append(_change(old_day, new_day, local_date_format))
    return changes


def _coalesced(actions):
    """
    Group the actions of the same entry by the same person in quick
    succession (each less than ``COALESCE`` after the previous one)
    """
    groups = []
    current = {}  # Entry ID: the group the entry's next action may join
    for action in actions:
        entry = action.row_data["id"]
        group = current.get(entry)
        if (
            group
            and group[-1].user_name == action.user_name
            and action.created_at - group[-1].created_at < COALESCE
        ):
            group.append(action)
        else:
            current[entry] = group = [action]
            groups.append(group)
    return groups


def _changes_by_others(model, *, owner, changes, start, end, users):
    """
    Entries of ``model`` someone else than their ``owner`` (before or after
    the change) has entered, deleted or changed between ``start`` and
    ``end``, from the audit log, coalesced. Yields the kind of change
    (I, U, D), the entry's data (after entering, before changing or
    deleting), the changes and the last action.
    """
    for group in _coalesced(
        LoggedAction.objects.for_model(model).filter(
            action__in=["I", "U", "D"], created_at__gte=start, created_at__lt=end
        )
    ):
        first, last = group[0], group[-1]
        old, new = first.row_data, last.new_row_data
        if first.action == "I":
            if last.action == "D":
                continue
            kind, shown, entry_changes = "I", new, []
        elif last.action == "D":
            kind, shown, entry_changes = "D", old, []
        else:
            kind, shown = "U", old
            if not (entry_changes := changes(old, new, users)):
                continue
        editor = audit_user_id(last.user_name or "")
        if {int(old[owner]), int(new[owner])} == {editor}:
            continue
        yield {
            "kind": kind,
            "data": shown,
            "old": old,
            "new": new,
            "changes": entry_changes,
            "changed_at": last.created_at,
            "editor": users.get(editor) or last.user_name or "?",
            "owner": users.get(int(shown[owner])),
        }


def changes_by_others(start, end):
    """
    Logged hours and absences others than the person they belong to have
    entered, deleted or changed in a way affecting the annual working time
    between ``start`` and ``end``
    """
    users = {user.pk: user for user in User.objects.all()}

    hours_rows = []
    for row in _changes_by_others(
        LoggedHours,
        owner="rendered_by_id",
        changes=_hours_changes,
        start=start,
        end=end,
        users=users,
    ):
        data = row["data"]
        hours_rows.append(
            row
            | {
                "rendered_on": _date(data["rendered_on"]),
                "hours": Decimal(data["hours"]),
                "service_id": int(data["service_id"]),
                "description": data["description"],
            }
        )
    services = Service.objects.select_related("project").in_bulk({
        row["service_id"] for row in hours_rows
    })
    for row in hours_rows:
        row["service"] = services.get(row["service_id"])

    absence_rows = []
    reasons = dict(Absence.REASON_CHOICES)
    for row in _changes_by_others(
        Absence,
        owner="user_id",
        changes=_absence_changes,
        start=start,
        end=end,
        users=users,
    ):
        if Absence.CORRECTION in {row["old"]["reason"], row["new"]["reason"]}:
            continue
        data = row["data"]
        # Neither the description nor anything else possibly being health data
        absence_rows.append(
            row
            | {
                "starts_on": _date(data["starts_on"]),
                "ends_on": _date(data["ends_on"] or data["starts_on"]),
                "days": Decimal(data["days"]),
                "reason": reasons[data["reason"]],
            }
        )

    return {"hours": hours_rows, "absences": absence_rows}


def changes_by_others_mails(*, today=None):
    """
    Send personnel administration a weekly mail (on Mondays) with the logged
    hours and absences of the previous week others have entered, deleted or
    changed so that the annual working time of the person changes
    """
    today = today or dt.date.today()
    if today.weekday() != 0:
        return
    if not (recipients := personnel_administration()):
        return

    end = timezone.make_aware(dt.datetime.combine(today, dt.time.min))
    start = end - dt.timedelta(days=7)
    for user in recipients:
        # The changes contain translated texts
        with override(user.language):
            changes = changes_by_others(start, end)
            if not changes["hours"] and not changes["absences"]:
                return
            render_to_mail(
                "awt/changes_by_others_mail",
                changes
                | {
                    "week_start": start.date(),
                    "WORKBENCH": settings.WORKBENCH,
                },
                to=[user.email],
            ).send()
