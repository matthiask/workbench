from django.conf.urls import url

from workbench.invoices.forms import (
    InvoiceSearchForm,
    InvoiceForm,
    CreatePersonInvoiceForm,
    InvoiceDeleteForm,
    ServiceForm,
)
from workbench.invoices.models import Invoice, Service
from workbench.invoices.views import InvoicePDFView, CreateRelatedView
from workbench.generic import ListView, CreateView, DetailView, UpdateView, DeleteView


urlpatterns = [
    url(
        r"^$",
        ListView.as_view(model=Invoice, search_form_class=InvoiceSearchForm),
        name="invoices_invoice_list",
    ),
    url(
        r"^picker/$",
        ListView.as_view(model=Invoice, template_name_suffix="_picker", paginate_by=15),
        name="invoices_invoice_picker",
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
        DeleteView.as_view(model=Invoice, form_class=InvoiceDeleteForm),
        name="invoices_invoice_delete",
    ),
    url(r"^(?P<pk>\d+)/pdf/$", InvoicePDFView.as_view(), name="invoices_invoice_pdf"),
    # Services
    url(
        r"^(?P<pk>\d+)/createservice/$",
        CreateRelatedView.as_view(model=Service, form_class=ServiceForm),
        name="invoices_invoice_createservice",
    ),
    url(
        r"^services/(?P<pk>[0-9]+)/update/$",
        UpdateView.as_view(model=Service, form_class=ServiceForm),
        name="invoices_service_update",
    ),
]
