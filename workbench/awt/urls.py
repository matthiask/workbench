from django.urls import re_path

from workbench import generic
from workbench.awt.forms import AbsenceForm, AbsenceSearchForm
from workbench.awt.models import Absence


urlpatterns = [
    re_path(
        r"^$",
        generic.ListView.as_view(
            model=Absence,
            search_form_class=AbsenceSearchForm,
            # show_create_button=False,
        ),
        name="awt_absence_list",
    ),
    re_path(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Absence),
        name="awt_absence_detail",
    ),
    re_path(
        r"^create/$",
        generic.CreateView.as_view(model=Absence, form_class=AbsenceForm),
        name="awt_absence_create",
    ),
    re_path(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=Absence, form_class=AbsenceForm),
        name="awt_absence_update",
    ),
    re_path(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Absence, template_name="modal_confirm_delete.html"
        ),
        name="awt_absence_delete",
    ),
]
