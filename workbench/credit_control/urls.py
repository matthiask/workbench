from django.urls import re_path

from workbench import generic
from workbench.accounts.features import bookkeeping_only
from workbench.credit_control.forms import (
    AccountStatementUploadForm,
    CreditEntryForm,
    CreditEntrySearchForm,
)
from workbench.credit_control.models import CreditEntry
from workbench.credit_control.views import (
    AccountStatementUploadView,
    AssignCreditEntriesView,
)


urlpatterns = [
    re_path(
        r"^$",
        generic.ListView.as_view(
            model=CreditEntry, search_form_class=CreditEntrySearchForm
        ),
        name="credit_control_creditentry_list",
    ),
    re_path(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=CreditEntry),
        name="credit_control_creditentry_detail",
    ),
    re_path(
        r"^create/$",
        bookkeeping_only(
            generic.CreateView.as_view(
                model=CreditEntry,
                form_class=CreditEntryForm,
                success_url="credit_control_creditentry_list",
            )
        ),
        name="credit_control_creditentry_create",
    ),
    re_path(
        r"^upload/$",
        bookkeeping_only(
            AccountStatementUploadView.as_view(
                model=CreditEntry,
                form_class=AccountStatementUploadForm,
                success_url="credit_control_creditentry_list",
            )
        ),
        name="credit_control_creditentry_upload",
    ),
    re_path(
        r"^(?P<pk>\d+)/update/$",
        bookkeeping_only(
            generic.UpdateView.as_view(model=CreditEntry, form_class=CreditEntryForm)
        ),
        name="credit_control_creditentry_update",
    ),
    re_path(
        r"^(?P<pk>\d+)/delete/$",
        bookkeeping_only(generic.DeleteView.as_view(model=CreditEntry)),
        name="credit_control_creditentry_delete",
    ),
    re_path(
        r"^assign/$",
        bookkeeping_only(AssignCreditEntriesView.as_view(model=CreditEntry)),
        name="credit_control_creditentry_assign",
    ),
]
