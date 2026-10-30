import datetime as dt

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import check_feature
from workbench.accounts.features import FEATURES
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.notes.forms import NoteForm
from workbench.notes.models import Note
from workbench.tools.api import Serialized, form_errors


router = Router(tags=["notes"])

# Notes are shown on these objects in the web interface, which require
# features
TARGETS = {
    "deal": (Deal, FEATURES.DEALS),
    "invoice": (Invoice, FEATURES.CONTROLLING),
    "recurring_invoice": (RecurringInvoice, FEATURES.CONTROLLING),
}


class NoteObject(Schema):
    type: str
    id: int
    name: str
    url: str


class NoteOut(Schema):
    id: int
    title: str
    description: str
    created_at: dt.datetime
    created_by: str
    object: NoteObject


def note_out(note, request, *, types):
    return {
        "id": note.id,
        "title": note.title,
        "description": note.description,
        "created_at": note.created_at,
        "created_by": note.created_by.get_short_name(),
        "object": {
            "type": types[note.content_type_id],
            "id": note.object_id,
            "name": str(note.content_object),
            "url": request.build_absolute_uri(note.content_object.get_absolute_url()),
        },
    }


def _content_types(user):
    """Content types of the objects whose notes the user may see"""
    return {
        ContentType.objects.get_for_model(model).pk: key
        for key, (model, feature) in TARGETS.items()
        if user.features[feature]
    }


def _visible(types):
    """Notes of existing objects the user may see; deleting objects doesn't
    delete their notes"""
    q = Q(pk__in=[])
    for content_type, key in types.items():
        q |= Q(
            content_type=content_type,
            object_id__in=TARGETS[key][0].objects.values("pk"),
        )
    return q


class NoteFilter(Schema):
    q: str = ""
    deal: int | None = None
    invoice: int | None = None
    recurring_invoice: int | None = None
    created_by: str | None = None


@router.get("/notes/", response=list[NoteOut])
@paginate
def note_list(request, filters: Query[NoteFilter]):
    """Notes on deals and invoices, newest first

    Notes on objects which require features the user hasn't got and notes of
    deleted objects are left out."""
    types = _content_types(request.user)
    notes = Note.objects.filter(_visible(types)).select_related(
        "created_by", "content_type"
    )
    objects = Q()
    for key in TARGETS:
        if object_id := getattr(filters, key):
            model = TARGETS[key][0]
            objects |= Q(
                content_type=ContentType.objects.get_for_model(model),
                object_id=object_id,
            )
    if objects:
        notes = notes.filter(objects)
    if filters.created_by:
        notes = notes.filter(created_by___short_name__iexact=filters.created_by)
    if filters.q:
        notes = notes.search(filters.q)
    return Serialized(
        notes.prefetch_related("content_object").order_by("-created_at", "-pk"),
        lambda note: note_out(note, request, types=types),
    )


class NoteIn(Schema):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    deal: int | None = None
    invoice: int | None = None
    recurring_invoice: int | None = None


@router.post("/notes/", response=NoteOut)
def note_create(request, data: NoteIn):
    """Add a note to exactly one deal, invoice or recurring invoice

    Like in the web interface, the owner of the object is notified by
    email."""
    targets = [key for key in TARGETS if getattr(data, key)]
    if len(targets) != 1:
        raise ValidationError([
            {
                "loc": ["body", "data"],
                "msg": _("Add the note to exactly one of %s.") % ", ".join(TARGETS),
            }
        ])
    key = targets[0]
    model, feature = TARGETS[key]
    check_feature(request.user, feature)

    form = NoteForm(
        {
            "title": data.title,
            "description": data.description,
            "content_type": ContentType.objects.get_for_model(model).pk,
            "object_id": getattr(data, key),
        },
        request=request,
    )
    if not form.is_valid():
        raise ValidationError(form_errors(form))
    return note_out(form.save(), request, types=_content_types(request.user))
