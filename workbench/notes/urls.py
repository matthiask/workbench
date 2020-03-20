from django.urls import re_path

from workbench import generic
from workbench.notes import views
from workbench.notes.forms import NoteForm, NoteSearchForm
from workbench.notes.models import Note


urlpatterns = [
    re_path(r"^add-note/$", views.add_note, name="notes_note_add"),
    re_path(
        r"^$",
        generic.ListView.as_view(
            model=Note, search_form_class=NoteSearchForm, show_create_button=False
        ),
        name="notes_note_list",
    ),
    re_path(
        r"(?P<pk>[0-9]+)/update/$",
        generic.UpdateView.as_view(model=Note, form_class=NoteForm),
        name="notes_note_update",
    ),
    re_path(
        r"^(?P<pk>[0-9]+)/delete/$",
        generic.DeleteView.as_view(
            model=Note, template_name="modal_confirm_delete.html"
        ),
        name="notes_note_delete",
    ),
]
