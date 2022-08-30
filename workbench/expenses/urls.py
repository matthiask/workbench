from django.urls import path

from workbench import generic
from workbench.expenses.forms import ExpenseReportForm, ExpenseReportSearchForm
from workbench.expenses.models import ExpenseReport
from workbench.expenses.views import ExpenseReportPDFView, convert


urlpatterns = [
    path(
        "",
        generic.ListView.as_view(
            model=ExpenseReport, search_form_class=ExpenseReportSearchForm
        ),
        name="expenses_expensereport_list",
    ),
    path(
        "<int:pk>/",
        generic.DetailView.as_view(model=ExpenseReport),
        name="expenses_expensereport_detail",
    ),
    path(
        "<int:pk>/pdf/",
        ExpenseReportPDFView.as_view(),
        name="expenses_expensereport_pdf",
    ),
    path(
        "create/",
        generic.CreateView.as_view(model=ExpenseReport, form_class=ExpenseReportForm),
        name="expenses_expensereport_create",
    ),
    path(
        "<int:pk>/update/",
        generic.UpdateView.as_view(model=ExpenseReport, form_class=ExpenseReportForm),
        name="expenses_expensereport_update",
    ),
    path(
        "<int:pk>/delete/",
        generic.DeleteView.as_view(model=ExpenseReport),
        name="expenses_expensereport_delete",
    ),
    path("convert/", convert, name="expenses_convert"),
]
