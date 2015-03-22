from django.conf.urls import url
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from invoices.forms import InvoiceForm
from invoices.models import Invoice
from invoices.views import InvoiceListView, InvoicePDFView
from tools.views import (
    DetailView, UpdateView, DeleteView, MessageView)


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
        MessageView.as_view(
            redirect_to='invoices_invoice_list',
            message=_(
                'Invoices cannot be added directly yet. Create invoices'
                ' by navigating to the organization or project first.'
            ),
            level=messages.WARNING,
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
