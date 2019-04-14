from django.conf.urls import url

from workbench import generic
from workbench.invoices.forms import (
    CreatePersonInvoiceForm,
    InvoiceDeleteForm,
    InvoiceForm,
    InvoiceSearchForm,
    ServiceForm,
)
from workbench.invoices.models import Invoice, Service
from workbench.invoices.views import InvoicePDFView


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=Invoice, search_form_class=InvoiceSearchForm),
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
        generic.DetailView.as_view(model=Invoice),
        name="invoices_invoice_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(model=Invoice, form_class=CreatePersonInvoiceForm),
        name="invoices_invoice_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=InvoiceForm, model=Invoice),
        name="invoices_invoice_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Invoice, delete_form_class=InvoiceDeleteForm),
        name="invoices_invoice_delete",
    ),
    url(r"^(?P<pk>\d+)/pdf/$", InvoicePDFView.as_view(), name="invoices_invoice_pdf"),
    # Services
    url(
        r"^(?P<pk>\d+)/createservice/$",
        generic.CreateRelatedView.as_view(
            model=Service, form_class=ServiceForm, related_model=Invoice
        ),
        name="invoices_invoice_createservice",
    ),
    url(
        r"^services/(?P<pk>[0-9]+)/update/$",
        generic.UpdateView.as_view(model=Service, form_class=ServiceForm),
        name="invoices_service_update",
    ),
]
