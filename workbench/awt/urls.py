from django.urls import path

from workbench import generic
from workbench.awt.changes import ABSENCE_WARNING
from workbench.awt.forms import AbsenceForm, AbsenceSearchForm
from workbench.awt.models import Absence, Holiday
from workbench.awt.views import (
    AbsenceDetailView,
    ReportedDeleteView,
    confirm_absence,
    suggested_days,
)


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
        AbsenceDetailView.as_view(),
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
        ReportedDeleteView.as_view(
            model=Absence, owner_field="user", warning=ABSENCE_WARNING
        ),
        name="awt_absence_delete",
    ),
    path("<int:pk>/confirm/", confirm_absence, name="awt_absence_confirm"),
    path("suggested-days/", suggested_days, name="awt_absence_suggested_days"),
    path(
        "holiday/<int:pk>/",
        generic.DetailView.as_view(model=Holiday),
        name="awt_holiday_detail",
    ),
]
