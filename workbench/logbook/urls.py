from django.shortcuts import redirect
from django.urls import path
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
    path("", lambda request: redirect("logbook_loggedhours_list"), name="logbook"),
    path(
        "hours/create/",
        create,
        {"viewname": "createhours"},
        name="logbook_loggedhours_create",
    ),
    path(
        "hours/",
        generic.ListView.as_view(
            model=LoggedHours,
            search_form_class=LoggedHoursSearchForm,
            show_create_button=False,
        ),
        name="logbook_loggedhours_list",
    ),
    path(
        "hours/<int:pk>/",
        generic.DetailView.as_view(model=LoggedHours),
        name="logbook_loggedhours_detail",
    ),
    path(
        "hours/<int:pk>/update/",
        generic.UpdateView.as_view(model=LoggedHours, form_class=LoggedHoursForm),
        name="logbook_loggedhours_update",
    ),
    path(
        "hours/<int:pk>/move/",
        generic.UpdateView.as_view(
            model=LoggedHours,
            form_class=LoggedHoursMoveForm,
            template_name="modalform.html",
            title=_("Move %(object)s"),
        ),
        name="logbook_loggedhours_move",
    ),
    path(
        "hours/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=LoggedHours, template_name="modal_confirm_delete.html"
        ),
        name="logbook_loggedhours_delete",
    ),
    path(
        "costs/create/",
        create,
        {"viewname": "createcost"},
        name="logbook_loggedcost_create",
    ),
    path(
        "costs/",
        generic.ListView.as_view(
            model=LoggedCost,
            search_form_class=LoggedCostSearchForm,
            show_create_button=False,
        ),
        name="logbook_loggedcost_list",
    ),
    path(
        "costs/<int:pk>/",
        generic.DetailView.as_view(model=LoggedCost),
        name="logbook_loggedcost_detail",
    ),
    path(
        "costs/<int:pk>/update/",
        generic.UpdateView.as_view(model=LoggedCost, form_class=LoggedCostForm),
        name="logbook_loggedcost_update",
    ),
    path(
        "hours/<int:pk>/move/",
        generic.UpdateView.as_view(
            model=LoggedCost,
            form_class=LoggedCostMoveForm,
            template_name="modalform.html",
            title=_("Move %(object)s"),
        ),
        name="logbook_loggedcost_move",
    ),
    path(
        "costs/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=LoggedCost, template_name="modal_confirm_delete.html"
        ),
        name="logbook_loggedcost_delete",
    ),
    path(
        "breaks/",
        generic.ListView.as_view(
            model=Break,
            search_form_class=BreakSearchForm,
            # show_create_button=False,
        ),
        name="logbook_break_list",
    ),
    path(
        "breaks/<int:pk>/",
        generic.DetailView.as_view(model=Break),
        name="logbook_break_detail",
    ),
    path(
        "breaks/create/",
        generic.CreateView.as_view(
            model=Break, form_class=BreakForm, template_name="modalform.html"
        ),
        name="logbook_break_create",
    ),
    path(
        "breaks/<int:pk>/update/",
        generic.UpdateView.as_view(
            model=Break, form_class=BreakForm, template_name="modalform.html"
        ),
        name="logbook_break_update",
    ),
    path(
        "breaks/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=Break, template_name="modal_confirm_delete.html"
        ),
        name="logbook_break_delete",
    ),
]
