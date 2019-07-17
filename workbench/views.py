from django.apps import apps
from django.contrib import messages
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from workbench.audit.models import LoggedAction
from workbench.contacts.models import (
    EmailAddress,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service
from workbench.tools.history import changes


def search(request):
    results = []
    q = request.GET.get("q", "")
    if q:
        results = [
            {
                "verbose_name_plural": queryset.model._meta.verbose_name_plural,
                "url": reverse(
                    "%s_%s_list"
                    % (queryset.model._meta.app_label, queryset.model._meta.model_name)
                ),
                "results": queryset.search(q)[:101],
            }
            for queryset in (
                Project.objects.select_related("owned_by"),
                Organization.objects.all(),
                Person.objects.active(),
                Invoice.objects.select_related("project", "owned_by"),
                RecurringInvoice.objects.all(),
                Offer.objects.select_related("project", "owned_by"),
                Deal.objects.all(),
            )
        ]
    else:
        messages.error(request, _("Search query missing."))

    return render(request, "search.html", {"query": q, "results": results})


HISTORY = {
    "accounts.user": {"exclude": {"is_admin", "last_login", "password"}},
    "contacts.person": {
        "exclude": {"_fts"},
        "related": [
            (PhoneNumber, "person_id"),
            (EmailAddress, "person_id"),
            (PostalAddress, "person_id"),
        ],
    },
    "invoices.invoice": {"exclude": {"_code", "_fts"}},
    "invoices.service": {"exclude": {"position"}},
    "offers.offer": {"exclude": {"_code"}},
    "projects.project": {
        "exclude": {"_code", "_fts"},
        "related": [(Offer, "project_id"), (Service, "project_id")],
    },
    "projects.service": {"exclude": {"position"}},
}


def history(request, label, attribute, id):
    model = apps.get_model(label)
    cfg = HISTORY.get(label, {})
    exclude = cfg.get("exclude", set())

    fields = [
        f.name
        for f in model._meta.get_fields()
        if hasattr(f, "attname") and not f.primary_key and f.name not in exclude
    ]

    instance = None
    if attribute == "id":
        try:
            instance = model._base_manager.get(**{attribute: id})
        except Exception:
            instance = None

    actions = LoggedAction.objects.for_model_id(model, **{attribute: id})

    return render(
        request,
        "history_modal.html",
        {
            "instance": instance,
            "changes": changes(model, fields, actions),
            "related": [
                (
                    model._meta.verbose_name_plural,
                    reverse(
                        "history",
                        args=(model._meta.label_lower, attribute, instance.pk),
                    ),
                )
                for model, attribute in cfg.get("related", [])
            ]
            if instance
            else [],
        },
    )
