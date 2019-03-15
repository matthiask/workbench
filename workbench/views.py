import re

from django.apps import apps
from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import gettext as _

from workbench.audit.models import LoggedAction
from workbench.contacts.models import Organization, Person
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.history import changes


def search(request):
    results = []
    q = request.GET.get("q", "")
    if q:
        results = [
            (queryset.model._meta.verbose_name_plural, queryset.search(q)[:101])
            for queryset in (
                Project.objects.select_related("owned_by"),
                Organization.objects.all(),
                Person.objects.all(),
                Invoice.objects.select_related("project", "owned_by"),
                Offer.objects.select_related("project"),
                Deal.objects.all(),
            )
        ]
    else:
        messages.error(request, _("Search query missing."))

    return render(request, "search.html", {"search": {"query": q, "results": results}})


HISTORY = {
    "awt.year": "",
    "awt.employment": "",
    "awt.absence": "",
    "contacts.organization": "",
    "contacts.person": "",
    "credit_control.creditentry": "",
    "deals.deal": "title, description, owned_by, stage, status, estimated_value",
    "invoices.invoice": (
        "invoiced_on, due_on, title, description, postal_address, owned_by,"
        " status, closed_on, subtotal, discount, tax_rate, total"
    ),
    "invoices.recurringinvoice": "",
    "logbook.loggedhours": "",
    "logbook.loggedcosts": "",
    "offers.offer": (
        "offered_on, closed_on, title, description, owned_by, status,"
        "subtotal, discount, tax_rate, total"
    ),
    "projects.project": (
        "customer, contact, title, description, owned_by, type, closed_on"
    ),
    "projects.service": "",
}


def history(request, label, pk):
    model = apps.get_model(label)
    fields = HISTORY.get(label)
    if not fields:
        fields = [
            f.name
            for f in model._meta.get_fields()
            if hasattr(f, "attname") and not f.primary_key
        ]
    else:
        fields = re.split(r"[\s,]+", fields)

    return render(
        request,
        "history_modal.html",
        {
            "changes": changes(
                model, fields, LoggedAction.objects.for_model_id(model, pk)
            )
        },
    )
