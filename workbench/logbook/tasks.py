import datetime as dt
from decimal import Decimal

from authlib.email import render_to_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import override

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.logbook.models import LoggedHours
from workbench.projects.models import Service
from workbench.tools.formats import hours, local_date_format


#: Changes of an entry by the same person this close to each other are one
COALESCE = dt.timedelta(hours=1)


def _changes(old, new, users):
    """What an update changed of the annual working time"""
    changes = []
    if Decimal(old["hours"]) != Decimal(new["hours"]):
        changes.append(
            f"{hours(Decimal(old['hours']))} → {hours(Decimal(new['hours']))}"
        )
    if old["rendered_by_id"] != new["rendered_by_id"]:
        changes.append(
            "{} → {}".format(
                users.get(int(old["rendered_by_id"]), old["rendered_by_id"]),
                users.get(int(new["rendered_by_id"]), new["rendered_by_id"]),
            )
        )
    # The annual working time sums up months, moving hours within a month
    # doesn't change it
    if old["rendered_on"][:7] != new["rendered_on"][:7]:
        changes.append(
            "{} → {}".format(
                local_date_format(dt.date.fromisoformat(old["rendered_on"])),
                local_date_format(dt.date.fromisoformat(new["rendered_on"])),
            )
        )
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


def changes_by_others(start, end):
    """
    Logged hours others than the person they belong to have logged, deleted
    or changed in a way affecting the annual working time (hours, person or
    month) between ``start`` and ``end``, from the audit log. Changes in quick
    succession are coalesced.
    """
    users = {user.pk: user for user in User.objects.all()}
    rows = []
    for group in _coalesced(
        LoggedAction.objects.for_model(LoggedHours).filter(
            action__in=["I", "U", "D"], created_at__gte=start, created_at__lt=end
        )
    ):
        first, last = group[0], group[-1]
        old, new = first.row_data, last.new_row_data
        if first.action == "I":
            if last.action == "D":
                continue
            kind, changes, shown = "I", [], new
        elif last.action == "D":
            kind, changes, shown = "D", [], old
        else:
            kind, changes, shown = "U", _changes(old, new, users), old
            if not changes:
                continue
        editor = audit_user_id(last.user_name or "")
        if {int(old["rendered_by_id"]), int(new["rendered_by_id"])} == {editor}:
            continue
        rows.append({
            "kind": kind,
            "changed_at": last.created_at,
            "editor": users.get(editor) or last.user_name or "?",
            "rendered_by": users.get(int(shown["rendered_by_id"])),
            "rendered_on": dt.date.fromisoformat(shown["rendered_on"]),
            "hours": Decimal(shown["hours"]),
            "service_id": int(shown["service_id"]),
            "description": shown["description"],
            "changes": changes,
        })

    services = Service.objects.select_related("project").in_bulk({
        row["service_id"] for row in rows
    })
    for row in rows:
        row["service"] = services.get(row["service_id"])
    return rows


def changes_by_others_mails(*, today=None):
    """
    Send personnel administration a weekly mail (on Mondays) with the logged
    hours of the previous week others have logged, deleted or changed so that
    the annual working time of the person changes
    """
    today = today or dt.date.today()
    if today.weekday() != 0:
        return
    recipients = [
        user
        for user in User.objects.active()
        if user.features[FEATURES.PERSONNEL_ADMINISTRATION]
    ]
    if not recipients:
        return

    end = timezone.make_aware(dt.datetime.combine(today, dt.time.min))
    start = end - dt.timedelta(days=7)
    if not (rows := changes_by_others(start, end)):
        return

    for user in recipients:
        with override(user.language):
            render_to_mail(
                "logbook/changes_by_others_mail",
                {
                    "rows": rows,
                    "week_start": start.date(),
                    "WORKBENCH": settings.WORKBENCH,
                },
                to=[user.email],
            ).send()
