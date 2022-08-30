from django.urls import path

from workbench import generic
from workbench.notes import views
from workbench.notes.forms import NoteForm, NoteSearchForm
from workbench.notes.models import Note


urlpatterns = [
    path("add-note/", views.add_note, name="notes_note_add"),
    path(
        "",
        generic.ListView.as_view(
            model=Note, search_form_class=NoteSearchForm, show_create_button=False
        ),
        name="notes_note_list",
    ),
    path(
        "<int:pk>/update/",
        generic.UpdateView.as_view(model=Note, form_class=NoteForm),
        name="notes_note_update",
    ),
    path(
        "<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=Note, template_name="modal_confirm_delete.html"
        ),
        name="notes_note_delete",
    ),
]
