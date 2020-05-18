from django.shortcuts import redirect
from django.urls import re_path
from django.utils.translation import gettext_lazy as _

from workbench import generic
from workbench.logbook.forms import (
    BreakForm,
    BreakSearchForm,
    LoggedCostForm,
    LoggedCostMoveForm,
    LoggedCostSearchForm,
    LoggedHoursForm,
    LoggedHoursMoveForm,
    LoggedHoursSearchForm,
)
from workbench.logbook.models import Break, LoggedCost, LoggedHours
from workbench.logbook.views import create


urlpatterns = [
    re_path(
        r"^$", lambda request: redirect("logbook_loggedhours_list"), name="logbook"
    ),
    re_path(
        r"^hours/create/$",
        create,
        {"viewname": "createhours"},
        name="logbook_loggedhours_create",
    ),
    re_path(
        r"^hours/$",
        generic.ListView.as_view(
            model=LoggedHours,
            search_form_class=LoggedHoursSearchForm,
            show_create_button=False,
        ),
        name="logbook_loggedhours_list",
    ),
    re_path(
        r"^hours/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=LoggedHours),
        name="logbook_loggedhours_detail",
    ),
    re_path(
        r"^hours/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=LoggedHours, form_class=LoggedHoursForm),
        name="logbook_loggedhours_update",
    ),
    re_path(
        r"^hours/(?P<pk>\d+)/move/$",
        generic.UpdateView.as_view(
            model=LoggedHours,
            form_class=LoggedHoursMoveForm,
            template_name="modalform.html",
            title=_("Move %(object)s"),
        ),
        name="logbook_loggedhours_move",
    ),
    re_path(
        r"^hours/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=LoggedHours, template_name="modal_confirm_delete.html"
        ),
        name="logbook_loggedhours_delete",
    ),
    re_path(
        r"^costs/create/$",
        create,
        {"viewname": "createcost"},
        name="logbook_loggedcost_create",
    ),
    re_path(
        r"^costs/$",
        generic.ListView.as_view(
            model=LoggedCost,
            search_form_class=LoggedCostSearchForm,
            show_create_button=False,
        ),
        name="logbook_loggedcost_list",
    ),
    re_path(
        r"^costs/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=LoggedCost),
        name="logbook_loggedcost_detail",
    ),
    re_path(
        r"^costs/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=LoggedCost, form_class=LoggedCostForm),
        name="logbook_loggedcost_update",
    ),
    re_path(
        r"^hours/(?P<pk>\d+)/move/$",
        generic.UpdateView.as_view(
            model=LoggedCost,
            form_class=LoggedCostMoveForm,
            template_name="modalform.html",
            title=_("Move %(object)s"),
        ),
        name="logbook_loggedcost_move",
    ),
    re_path(
        r"^costs/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=LoggedCost, template_name="modal_confirm_delete.html"
        ),
        name="logbook_loggedcost_delete",
    ),
    re_path(
        r"^breaks/$",
        generic.ListView.as_view(
            model=Break,
            search_form_class=BreakSearchForm,
            # show_create_button=False,
        ),
        name="logbook_break_list",
    ),
    re_path(
        r"^breaks/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Break),
        name="logbook_break_detail",
    ),
    re_path(
        r"^breaks/create/$",
        generic.CreateView.as_view(
            model=Break, form_class=BreakForm, template_name="modalform.html"
        ),
        name="logbook_break_create",
    ),
    re_path(
        r"^breaks/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=Break, form_class=BreakForm, template_name="modalform.html"
        ),
        name="logbook_break_update",
    ),
    re_path(
        r"^breaks/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Break, template_name="modal_confirm_delete.html"
        ),
        name="logbook_break_delete",
    ),
]
