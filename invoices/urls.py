from django.conf.urls import url

from invoices.forms import InvoiceForm
from invoices.models import Invoice
from invoices.views import InvoiceListView, InvoicePDFView
from tools.views import (
    DetailView, CreateView, UpdateView, DeleteView)


urlpatterns = [
    url(
        r'^$',
        InvoiceListView.as_view(),
        name='invoices_invoice_list'),
    url(
        r'^(?P<pk>\d+)/$',
        DetailView.as_view(model=Invoice),
        name='invoices_invoice_detail'),
    url(
        r'^create/$',
        CreateView.as_view(
            form_class=InvoiceForm,
            model=Invoice,
        ),
        name='invoices_invoice_create'),
    url(
        r'^(?P<pk>\d+)/update/$',
        UpdateView.as_view(
            form_class=InvoiceForm,
            model=Invoice,
        ),
        name='invoices_invoice_update'),
    url(
        r'^(?P<pk>\d+)/delete/$',
        DeleteView.as_view(model=Invoice),
        name='invoices_invoice_delete'),

    url(
        r'^(?P<pk>\d+)/pdf/$',
        InvoicePDFView.as_view(),
        name='invoices_invoice_pdf'),
]
