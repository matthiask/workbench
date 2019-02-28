from django.apps import apps
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import ugettext as _

from workbench.contacts.models import Organization, Person
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import Project


def search(request):
    results = []
    q = request.GET.get("q", "")
    if q:
        results = [
            (queryset.model._meta.verbose_name_plural, queryset.search(q)[:101])
            for queryset in (
                Organization.objects.all(),
                Person.objects.all(),
                Project.objects.select_related("owned_by"),
                Invoice.objects.select_related("project"),
                Deal.objects.all(),
                Offer.objects.all(),
            )
        ]
    else:
        messages.error(request, _("Search query missing."))

    return render(request, "search.html", {"search": {"query": q, "results": results}})


HISTORY = {
    "contacts.organization": "",
    "contacts.person": "",
    "deals.deal": "title, description, owned_by, stage, status, estimated_value",
    "invoices.invoice": (
        "invoiced_on, due_on, title, description, postal_address, owned_by,"
        " status, closed_on, subtotal, discount, tax_rate, total"
    ),
    "logbook.loggedhours": "",
    "logbook.loggedcosts": "",
    "offers.offer": (
        "offered_on, closed_on, title, description, owned_by, status,"
        "subtotal, discount, tax_rate, total"
    ),
    "projects.project": (
        "customer, contact, title, description, owned_by, status,"
        "invoicing, maintenance"
    ),
    "projects.task": "",
}


def history(request, label, pk):
    try:
        fields = HISTORY[label]
    except KeyError:
        raise Http404("No or disallowed history: %s" % label)

    instance = get_object_or_404(apps.get_model(label), pk=pk)

    return render(
        request, "history_modal.html", {"instance": instance, "fields": fields}
    )
