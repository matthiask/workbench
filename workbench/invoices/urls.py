from django.conf.urls import url

from workbench.invoices.forms import (
    InvoiceSearchForm,
    InvoiceForm,
    CreatePersonInvoiceForm,
)
from workbench.invoices.models import Invoice
from workbench.invoices.views import InvoicePDFView
from workbench.generic import ListView, CreateView, DetailView, UpdateView, DeleteView


urlpatterns = [
    url(
        r"^$",
        ListView.as_view(model=Invoice, search_form_class=InvoiceSearchForm),
        name="invoices_invoice_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        DetailView.as_view(model=Invoice),
        name="invoices_invoice_detail",
    ),
    url(
        r"^create/$",
        CreateView.as_view(model=Invoice, form_class=CreatePersonInvoiceForm),
        name="invoices_invoice_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        UpdateView.as_view(form_class=InvoiceForm, model=Invoice),
        name="invoices_invoice_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        DeleteView.as_view(model=Invoice),
        name="invoices_invoice_delete",
    ),
    url(r"^(?P<pk>\d+)/pdf/$", InvoicePDFView.as_view(), name="invoices_invoice_pdf"),
]
