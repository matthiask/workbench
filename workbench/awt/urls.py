from django.conf.urls import url

from workbench import generic
from workbench.awt.forms import AbsenceSearchForm, AbsenceForm
from workbench.awt.models import Absence, Year
from workbench.awt.views import ReportView


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
        generic.MessageView.as_view(
            redirect_to="awt_absence_list", message="Not implemented yet."
        ),
        name="awt_absence_delete",
    ),
    url(r"^report/$", ReportView.as_view(model=Year), name="awt_year_report"),
]
