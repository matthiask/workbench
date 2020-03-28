from django.conf.urls import url
from django.shortcuts import redirect

from workbench import generic
from workbench.logbook.forms import (
    BreakForm,
    BreakSearchForm,
    LoggedCostForm,
    LoggedCostSearchForm,
    LoggedHoursForm,
    LoggedHoursSearchForm,
)
from workbench.logbook.models import Break, LoggedCost, LoggedHours
from workbench.logbook.views import create


urlpatterns = [
    url(r"^$", lambda request: redirect("logbook_loggedhours_list"), name="logbook"),
    url(
        r"^hours/create/$",
        create,
        {"viewname": "createhours"},
        name="logbook_loggedhours_create",
    ),
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
        generic.UpdateView.as_view(model=LoggedHours, form_class=LoggedHoursForm),
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
        r"^costs/create/$",
        create,
        {"viewname": "createcost"},
        name="logbook_loggedcost_create",
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
        generic.UpdateView.as_view(model=LoggedCost, form_class=LoggedCostForm),
        name="logbook_loggedcost_update",
    ),
    url(
        r"^costs/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=LoggedCost, template_name="modal_confirm_delete.html"
        ),
        name="logbook_loggedcost_delete",
    ),
    url(
        r"^breaks/$",
        generic.ListView.as_view(
            model=Break,
            search_form_class=BreakSearchForm,
            # show_create_button=False,
        ),
        name="logbook_break_list",
    ),
    url(
        r"^breaks/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Break),
        name="logbook_break_detail",
    ),
    url(
        r"^breaks/create/$",
        generic.CreateView.as_view(
            model=Break, form_class=BreakForm, template_name="modalform.html"
        ),
        name="logbook_break_create",
    ),
    url(
        r"^breaks/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=Break, form_class=BreakForm, template_name="modalform.html"
        ),
        name="logbook_break_update",
    ),
    url(
        r"^breaks/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Break, template_name="modal_confirm_delete.html"
        ),
        name="logbook_break_delete",
    ),
]
