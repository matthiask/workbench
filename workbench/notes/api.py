import datetime as dt
from typing import Literal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import check_feature
from workbench.notes.forms import NoteForm
from workbench.notes.models import TARGETS, Note, visible_content_types
from workbench.tools.api import (
    DateRangeFilter,
    InputSchema,
    ProjectID,
    SearchQuery,
    Serialized,
    ShortName,
    filter_date_range,
    form_errors,
    user_by_short_name,
)


router = Router(tags=["notes"])


class NoteObject(Schema):
    type: Literal[tuple(TARGETS)]
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


class NoteFilter(DateRangeFilter):
    q: SearchQuery = ""
    deal: int | None = Field(default=None, description="ID of the deal.")
    invoice: int | None = Field(default=None, description="ID of the invoice.")
    recurring_invoice: int | None = Field(
        default=None, description="ID of the recurring invoice."
    )
    project: ProjectID = None
    created_by: ShortName = None


@router.get("/notes/", response=list[NoteOut])
@paginate
def note_list(request, filters: Query[NoteFilter]):
    """Notes on deals, invoices and projects, newest first; the period filters the
    creation date

    Notes on objects which require features the user hasn't got and notes of
    deleted objects are left out."""
    types = visible_content_types(request.user)
    notes = Note.objects.visible(types).select_related("created_by", "content_type")
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
        notes = notes.filter(
            created_by=user_by_short_name(filters.created_by, param="created_by")
        )
    if filters.q:
        notes = notes.search(filters.q)
    notes = filter_date_range(notes, filters, "created_at__date")
    return Serialized(
        notes.with_content_objects().order_by("-created_at", "-pk"),
        lambda note: note_out(note, request, types=types),
    )


class NoteIn(InputSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    deal: int | None = None
    invoice: int | None = None
    recurring_invoice: int | None = None
    project: ProjectID = None


@router.post("/notes/", response=NoteOut)
def note_create(request, data: NoteIn):
    """Add a note to exactly one deal, invoice, recurring invoice or project

    The description is Markdown. Like in the web interface, the owner of the
    object finds it in the daily notes digest mail."""
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
    return note_out(form.save(), request, types=visible_content_types(request.user))
