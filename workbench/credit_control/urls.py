from django.conf.urls import url

from workbench import generic
from workbench.credit_control.forms import (
    AccountStatementSearchForm,
    AccountStatementForm,
)
from workbench.credit_control.models import AccountStatement, CreditEntry
from workbench.credit_control.views import AssignCreditEntriesView


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(
            model=AccountStatement, search_form_class=AccountStatementSearchForm
        ),
        name="credit_control_accountstatement_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=AccountStatement),
        name="credit_control_accountstatement_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(
            model=AccountStatement, form_class=AccountStatementForm
        ),
        name="credit_control_accountstatement_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=AccountStatement, form_class=AccountStatementForm
        ),
        name="credit_control_accountstatement_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=AccountStatement),
        name="credit_control_accountstatement_delete",
    ),
    url(
        r"^assign/$",
        AssignCreditEntriesView.as_view(model=CreditEntry),
        name="credit_control_creditentry_assign",
    ),
]
