from django.conf.urls import url
from django.shortcuts import redirect

from workbench import generic
from workbench.logbook.forms import (
    LoggedCostForm,
    LoggedCostSearchForm,
    LoggedHoursForm,
    LoggedHoursSearchForm,
)
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.logbook.views import createhours


urlpatterns = [
    url(r"^$", lambda request: redirect("logbook_loggedhours_list"), name="logbook"),
    url(r"^create/$", createhours, name="logbook_loggedhours_create"),
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
        generic.DeleteView.as_view(
            model=LoggedHours, template_name="modal_confirm_delete.html"
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
        generic.DeleteView.as_view(
            model=LoggedCost, template_name="modal_confirm_delete.html"
        ),
        name="logbook_loggedcost_delete",
    ),
]
