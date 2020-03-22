from django.conf.urls import url

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
    url(
        r"^$",
        controlling_only(
            generic.ListView.as_view(model=Invoice, search_form_class=InvoiceSearchForm)
        ),
        name="invoices_invoice_list",
    ),
    url(
        r"^autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Invoice,
            queryset=Invoice.objects.select_related("project", "owned_by"),
        ),
        name="invoices_invoice_autocomplete",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        controlling_only(generic.DetailView.as_view(model=Invoice)),
        name="invoices_invoice_detail",
    ),
    url(
        r"^create/$",
        controlling_only(
            generic.CreateView.as_view(
                model=Invoice, form_class=CreatePersonInvoiceForm
            )
        ),
        name="invoices_invoice_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        controlling_only(
            generic.UpdateView.as_view(form_class=InvoiceForm, model=Invoice)
        ),
        name="invoices_invoice_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        controlling_only(
            generic.DeleteView.as_view(
                model=Invoice, delete_form_class=InvoiceDeleteForm
            )
        ),
        name="invoices_invoice_delete",
    ),
    url(
        r"^(?P<pk>\d+)/pdf/$",
        controlling_only(views.InvoicePDFView.as_view()),
        name="invoices_invoice_pdf",
    ),
    url(
        r"^(?P<pk>\d+)/xlsx/$",
        controlling_only(views.InvoiceXLSXView.as_view()),
        name="invoices_invoice_xlsx",
    ),
    # Services
    url(
        r"^(?P<pk>\d+)/createservice/$",
        controlling_only(
            generic.CreateRelatedView.as_view(
                model=Service, form_class=ServiceForm, related_model=Invoice
            )
        ),
        name="invoices_invoice_createservice",
    ),
    url(
        r"^services/(?P<pk>[0-9]+)/update/$",
        controlling_only(
            generic.UpdateView.as_view(model=Service, form_class=ServiceForm)
        ),
        name="invoices_service_update",
    ),
    url(r"^reminders/$", bookkeeping_only(views.reminders), name="invoices_reminders"),
    url(
        r"^dunning-letter/(?P<customer_id>[0-9]+)/$",
        bookkeeping_only(views.dunning_letter),
        name="invoices_dunning_letter",
    ),
]
