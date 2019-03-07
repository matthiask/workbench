from django.conf.urls import url

from workbench import generic
from workbench.invoices.forms import (
    RecurringInvoiceSearchForm,
    CreateRecurringInvoiceForm,
    RecurringInvoiceForm,
)
from workbench.invoices.models import RecurringInvoice
from workbench.invoices.views import (
    RecurringInvoiceDetailView,
    RecurringInvoiceCreateView,
)


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(
            model=RecurringInvoice, search_form_class=RecurringInvoiceSearchForm
        ),
        name="invoices_recurringinvoice_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        RecurringInvoiceDetailView.as_view(model=RecurringInvoice),
        name="invoices_recurringinvoice_detail",
    ),
    url(
        r"^create/$",
        RecurringInvoiceCreateView.as_view(
            model=RecurringInvoice, form_class=CreateRecurringInvoiceForm
        ),
        name="invoices_recurringinvoice_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=RecurringInvoice, form_class=RecurringInvoiceForm
        ),
        name="invoices_recurringinvoice_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=RecurringInvoice),
        name="invoices_recurringinvoice_delete",
    ),
]
