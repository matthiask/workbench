from django.conf.urls import url
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from invoices.forms import InvoiceSearchForm, InvoiceForm
from invoices.models import Invoice
from invoices.views import InvoicePDFView
from tools.views import (
    ListView, DetailView, UpdateView, DeleteView, MessageView, HistoryView)


urlpatterns = [
    url(
        r'^$',
        ListView.as_view(
            model=Invoice,
            search_form_class=InvoiceSearchForm,
            select_related=(
                'customer',
                'contact__organization',
                'project',
                'owned_by',
            ),
        ),
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

    url(
        r'^(?P<pk>\d+)/history/$',
        HistoryView.as_view(model=Invoice),
        name='invoices_invoice_history'),
]
