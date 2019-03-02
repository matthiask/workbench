from django.conf.urls import url
from django.shortcuts import redirect

from workbench import generic
from workbench.logbook.forms import (
    LoggedHoursSearchForm,
    LoggedHoursForm,
    LoggedCostSearchForm,
    LoggedCostForm,
)
from workbench.logbook.models import LoggedHours, LoggedCost


urlpatterns = [
    url(r"^$", lambda request: redirect("logbook_loggedhours_list"), name="logbook"),
    url(
        r"^hours/$",
        generic.ListView.as_view(
            model=LoggedHours,
            search_form_class=LoggedHoursSearchForm,
            show_create_button=False,
        ),
        name="logbook_loggedhours_list",
    ),
    url(
        r"^hours/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=LoggedHours),
        name="logbook_loggedhours_detail",
    ),
    url(
        r"^hours/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=LoggedHours,
            form_class=LoggedHoursForm,
            template_name="modalform.html",
        ),
        name="logbook_loggedhours_update",
    ),
    url(
        r"^hours/(?P<pk>\d+)/delete/$",
        generic.MessageView.as_view(
            redirect_to="logbook_loggedhours_list", message="Not implemented yet."
        ),
        name="logbook_loggedhours_delete",
    ),
    url(
        r"^costs/$",
        generic.ListView.as_view(
            model=LoggedCost,
            search_form_class=LoggedCostSearchForm,
            show_create_button=False,
        ),
        name="logbook_loggedcost_list",
    ),
    url(
        r"^costs/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=LoggedCost),
        name="logbook_loggedcost_detail",
    ),
    url(
        r"^costs/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=LoggedCost, form_class=LoggedCostForm, template_name="modalform.html"
        ),
        name="logbook_loggedcost_update",
    ),
    url(
        r"^costs/(?P<pk>\d+)/delete/$",
        generic.MessageView.as_view(
            redirect_to="logbook_loggedcost_list", message="Not implemented yet."
        ),
        name="logbook_loggedcost_delete",
    ),
]
