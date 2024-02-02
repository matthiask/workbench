from django.apps import apps
from django.http import Http404
from django.shortcuts import get_object_or_404, render


HISTORY = {
    "calendar.day": "",
    "contacts.organization": "",
    "contacts.person": "",
    "deals.deal": "title, description, owned_by, stage, status, estimated_value",
    "invoices.invoice": (
        "invoiced_on, due_on, title, description, postal_address, owned_by,"
        " status, closed_at, subtotal, discount, tax_rate, total"
    ),
    "logbook.loggedhours": "",
    "logbook.loggedcosts": "",
    "offers.offer": (
        "offered_on, closed_at, title, description, owned_by, status,"
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
        raise Http404("No or disallowed history: %s" % label) from None

    instance = get_object_or_404(apps.get_model(label), pk=pk)

    return render(
        request, "history_modal.html", {"instance": instance, "fields": fields}
    )
