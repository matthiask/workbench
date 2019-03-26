from django.conf.urls import url

from workbench import generic
from workbench.awt.forms import AbsenceForm, AbsenceSearchForm
from workbench.awt.models import Absence


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(
            model=Absence,
            search_form_class=AbsenceSearchForm,
            # show_create_button=False,
        ),
        name="awt_absence_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Absence),
        name="awt_absence_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(model=Absence, form_class=AbsenceForm),
        name="awt_absence_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=Absence, form_class=AbsenceForm),
        name="awt_absence_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Absence, template_name="modal_confirm_delete.html"
        ),
        name="awt_absence_delete",
    ),
]
