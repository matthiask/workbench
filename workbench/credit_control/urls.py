from django.conf.urls import url

from workbench import generic
from workbench.accounts.features import book_keeping_only
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
    url(
        r"^$",
        generic.ListView.as_view(
            model=CreditEntry, search_form_class=CreditEntrySearchForm
        ),
        name="credit_control_creditentry_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=CreditEntry),
        name="credit_control_creditentry_detail",
    ),
    url(
        r"^create/$",
        book_keeping_only(
            generic.CreateView.as_view(
                model=CreditEntry,
                form_class=CreditEntryForm,
                success_url="credit_control_creditentry_list",
            )
        ),
        name="credit_control_creditentry_create",
    ),
    url(
        r"^upload/$",
        book_keeping_only(
            AccountStatementUploadView.as_view(
                model=CreditEntry,
                form_class=AccountStatementUploadForm,
                success_url="credit_control_creditentry_list",
            )
        ),
        name="credit_control_creditentry_upload",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        book_keeping_only(
            generic.UpdateView.as_view(model=CreditEntry, form_class=CreditEntryForm)
        ),
        name="credit_control_creditentry_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        book_keeping_only(generic.DeleteView.as_view(model=CreditEntry)),
        name="credit_control_creditentry_delete",
    ),
    url(
        r"^assign/$",
        book_keeping_only(AssignCreditEntriesView.as_view(model=CreditEntry)),
        name="credit_control_creditentry_assign",
    ),
]
