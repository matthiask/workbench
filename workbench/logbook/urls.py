from django.conf.urls import url

from workbench import generic
from workbench.logbook.forms import LoggedHoursSearchForm, LoggedHoursForm
from workbench.logbook.models import LoggedHours


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(
            model=LoggedHours,
            search_form_class=LoggedHoursSearchForm,
            show_create_button=False,
        ),
        name="logbook_loggedhours_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=LoggedHours),
        name="logbook_loggedhours_detail",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=LoggedHours,
            form_class=LoggedHoursForm,
            template_name="modalform.html",
        ),
        name="logbook_loggedhours_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.MessageView.as_view(
            redirect_to="logbook_loggedhours_list", message="Not implemented yet."
        ),
        name="logbook_loggedhours_delete",
    ),
]
