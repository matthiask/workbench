from django.conf.urls import url

from workbench import generic
from workbench.expenses.forms import ExpenseReportForm
from workbench.expenses.models import ExpenseReport
from workbench.expenses.views import ExpenseReportPDFView


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=ExpenseReport),
        name="expenses_expensereport_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=ExpenseReport),
        name="expenses_expensereport_detail",
    ),
    url(
        r"^(?P<pk>\d+)/pdf/$",
        ExpenseReportPDFView.as_view(),
        name="expenses_expensereport_pdf",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(model=ExpenseReport, form_class=ExpenseReportForm),
        name="expenses_expensereport_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=ExpenseReport, form_class=ExpenseReportForm),
        name="expenses_expensereport_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=ExpenseReport),
        name="expenses_expensereport_delete",
    ),
]
