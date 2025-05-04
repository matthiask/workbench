from django.urls import path

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
    export_debtors,
)


urlpatterns = [
    path(
        "",
        generic.ListView.as_view(
            model=CreditEntry, search_form_class=CreditEntrySearchForm
        ),
        name="credit_control_creditentry_list",
    ),
    path(
        "<int:pk>/",
        generic.DetailView.as_view(model=CreditEntry),
        name="credit_control_creditentry_detail",
    ),
    path(
        "create/",
        bookkeeping_only(
            generic.CreateView.as_view(
                model=CreditEntry,
                form_class=CreditEntryForm,
                success_url="credit_control_creditentry_list",
            )
        ),
        name="credit_control_creditentry_create",
    ),
    path(
        "upload/",
        bookkeeping_only(
            AccountStatementUploadView.as_view(
                model=CreditEntry,
                form_class=AccountStatementUploadForm,
                success_url="credit_control_creditentry_list",
            )
        ),
        name="credit_control_creditentry_upload",
    ),
    path(
        "<int:pk>/update/",
        bookkeeping_only(
            generic.UpdateView.as_view(model=CreditEntry, form_class=CreditEntryForm)
        ),
        name="credit_control_creditentry_update",
    ),
    path(
        "<int:pk>/delete/",
        bookkeeping_only(generic.DeleteView.as_view(model=CreditEntry)),
        name="credit_control_creditentry_delete",
    ),
    path(
        "assign/",
        bookkeeping_only(AssignCreditEntriesView.as_view(model=CreditEntry)),
        name="credit_control_creditentry_assign",
    ),
    path(
        "export-debtors/",
        bookkeeping_only(export_debtors),
        name="credit_control_export_debtors",
    ),
]
