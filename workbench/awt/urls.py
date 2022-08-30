from django.urls import path

from workbench import generic
from workbench.awt.forms import AbsenceForm, AbsenceSearchForm
from workbench.awt.models import Absence


urlpatterns = [
    path(
        "",
        generic.ListView.as_view(
            model=Absence,
            search_form_class=AbsenceSearchForm,
            # show_create_button=False,
        ),
        name="awt_absence_list",
    ),
    path(
        "<int:pk>/",
        generic.DetailView.as_view(model=Absence),
        name="awt_absence_detail",
    ),
    path(
        "create/",
        generic.CreateView.as_view(model=Absence, form_class=AbsenceForm),
        name="awt_absence_create",
    ),
    path(
        "<int:pk>/update/",
        generic.UpdateView.as_view(model=Absence, form_class=AbsenceForm),
        name="awt_absence_update",
    ),
    path(
        "<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=Absence, template_name="modal_confirm_delete.html"
        ),
        name="awt_absence_delete",
    ),
]
