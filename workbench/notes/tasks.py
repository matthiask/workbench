import datetime as dt
from collections import defaultdict

from authlib.email import render_to_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import override

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction
from workbench.notes.models import Note, visible_content_types


def send_notes_digest(*, day=None):
    """
    Send owners of deals, invoices and projects one mail with the notes
    others added or edited on that day (default: yesterday), found in the
    audit log. The mail contains titles, the beginning of the descriptions
    and links to Workbench, only of objects the owners may see.
    """
    day = day or dt.date.today() - dt.timedelta(days=1)
    start = timezone.make_aware(dt.datetime.combine(day, dt.time.min))
    actions = LoggedAction.objects.for_model(Note).filter(
        action__in=["I", "U"],
        created_at__gte=start,
        created_at__lt=start + dt.timedelta(days=1),
    )

    by_note = defaultdict(set)
    for action in actions:
        by_note[int(action.row_data["id"])].add(action.user_id)
    if not by_note:
        return

    users = {user.id: user for user in User.objects.all()}
    by_owner = defaultdict(list)
    visible = {}  # Content types per owner, depending on their features
    for note in (
        Note.objects
        .filter(pk__in=by_note)
        .with_content_objects()
        .select_related("created_by")
        .order_by("pk")
    ):
        owner = getattr(note.content_object, "owned_by", None)
        authors = {users[pk] for pk in by_note[note.pk] if pk in users}
        if owner is None or not owner.is_active or authors <= {owner}:
            continue
        if owner not in visible:
            visible[owner] = visible_content_types(owner)
        if note.content_type_id not in visible[owner]:
            continue
        by_owner[owner].append((note, sorted(authors - {owner})))

    for owner, notes in by_owner.items():
        with override(owner.language):
            render_to_mail(
                "notes/notes_digest",
                {
                    "owner": owner,
                    "notes": notes,
                    "day": day,
                    "WORKBENCH": settings.WORKBENCH,
                },
                to=[owner.email],
                reply_to=[owner.email],
            ).send()
