from django.urls import re_path

from workbench import generic
from workbench.expenses.forms import ExpenseReportForm, ExpenseReportSearchForm
from workbench.expenses.models import ExpenseReport
from workbench.expenses.views import ExpenseReportPDFView, convert


urlpatterns = [
    re_path(
        r"^$",
        generic.ListView.as_view(
            model=ExpenseReport, search_form_class=ExpenseReportSearchForm
        ),
        name="expenses_expensereport_list",
    ),
    re_path(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=ExpenseReport),
        name="expenses_expensereport_detail",
    ),
    re_path(
        r"^(?P<pk>\d+)/pdf/$",
        ExpenseReportPDFView.as_view(),
        name="expenses_expensereport_pdf",
    ),
    re_path(
        r"^create/$",
        generic.CreateView.as_view(model=ExpenseReport, form_class=ExpenseReportForm),
        name="expenses_expensereport_create",
    ),
    re_path(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=ExpenseReport, form_class=ExpenseReportForm),
        name="expenses_expensereport_update",
    ),
    re_path(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=ExpenseReport),
        name="expenses_expensereport_delete",
    ),
    re_path(r"^convert/$", convert, name="expenses_convert"),
]
