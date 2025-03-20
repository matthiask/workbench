from django.urls import path

from workbench import generic
from workbench.accounts.features import bookkeeping_only, controlling_only
from workbench.invoices import views
from workbench.invoices.forms import (
    CreatePersonInvoiceForm,
    InvoiceDeleteForm,
    InvoiceForm,
    InvoiceSearchForm,
    ServiceForm,
)
from workbench.invoices.models import Invoice, Service


urlpatterns = [
    path(
        "",
        controlling_only(
            generic.ListView.as_view(model=Invoice, search_form_class=InvoiceSearchForm)
        ),
        name="invoices_invoice_list",
    ),
    path(
        "autocomplete/",
        generic.AutocompleteView.as_view(
            model=Invoice,
            queryset=Invoice.objects.select_related("project", "owned_by"),
        ),
        name="invoices_invoice_autocomplete",
    ),
    path(
        "<int:pk>/",
        controlling_only(generic.DetailView.as_view(model=Invoice)),
        name="invoices_invoice_detail",
    ),
    path(
        "create/",
        controlling_only(
            generic.CreateView.as_view(
                model=Invoice, form_class=CreatePersonInvoiceForm
            )
        ),
        name="invoices_invoice_create",
    ),
    path(
        "<int:pk>/update/",
        controlling_only(
            generic.UpdateView.as_view(form_class=InvoiceForm, model=Invoice)
        ),
        name="invoices_invoice_update",
    ),
    path(
        "<int:pk>/delete/",
        controlling_only(
            generic.DeleteView.as_view(
                model=Invoice, delete_form_class=InvoiceDeleteForm
            )
        ),
        name="invoices_invoice_delete",
    ),
    path(
        "<int:pk>/pdf/",
        controlling_only(views.InvoicePDFView.as_view()),
        name="invoices_invoice_pdf",
    ),
    path(
        "<int:pk>/xlsx/",
        controlling_only(views.InvoiceXLSXView.as_view()),
        name="invoices_invoice_xlsx",
    ),
    # Services
    path(
        "<int:pk>/createservice/",
        controlling_only(
            generic.CreateRelatedView.as_view(
                model=Service, form_class=ServiceForm, related_model=Invoice
            )
        ),
        name="invoices_invoice_createservice",
    ),
    path(
        "services/<int:pk>/update/",
        controlling_only(
            generic.UpdateView.as_view(model=Service, form_class=ServiceForm)
        ),
        name="invoices_service_update",
    ),
    path(
        "services/<int:pk>/delete/",
        controlling_only(
            generic.DeleteView.as_view(
                model=Service, template_name="modal_confirm_delete.html"
            ),
        ),
        name="invoices_service_delete",
    ),
    path("reminders/", bookkeeping_only(views.reminders), name="invoices_reminders"),
    path(
        "reminders/<int:contact_id>/",
        bookkeeping_only(views.dunning_letter),
        name="invoices_dunning_letter",
    ),
]
