from django.apps import apps
from django.contrib import messages
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.audit.models import LoggedAction
from workbench.contacts.models import Organization, Person
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.history import HISTORY, changes


def search(request):
    results = []
    q = request.GET.get("q", "")
    if q:
        sources = [
            Project.objects.select_related("owned_by"),
            Organization.objects.all(),
            Person.objects.active(),
        ]
        if request.user.features[FEATURES.CONTROLLING]:
            sources.extend(
                [
                    Invoice.objects.select_related("project", "owned_by"),
                    RecurringInvoice.objects.all(),
                    Offer.objects.select_related("project", "owned_by").order_by("-pk"),
                    Deal.objects.order_by("-pk"),
                ]
            )
        results = [
            {
                "verbose_name_plural": queryset.model._meta.verbose_name_plural,
                "url": reverse(
                    "%s_%s_list"
                    % (queryset.model._meta.app_label, queryset.model._meta.model_name)
                ),
                "results": queryset.search(q)[:101],
            }
            for queryset in sources
        ]
    else:
        messages.error(request, _("Search query missing."))

    return render(request, "search.html", {"query": q, "results": results})


DB_TABLE_TO_MODEL = {model._meta.db_table: model for model in apps.get_models()}


def history(request, db_table, attribute, id):
    try:
        model = DB_TABLE_TO_MODEL[db_table]
        cfg = HISTORY[model]
    except KeyError:
        raise Http404

    if callable(cfg):
        cfg = cfg(request.user)
    fields = cfg.get("fields", set())

    fields = [
        f
        for f in model._meta.get_fields()
        if hasattr(f, "attname") and not f.primary_key and f.name in fields
    ]

    instance = None
    title = None
    related = []

    if attribute == "id":
        try:
            instance = model._base_manager.get(**{attribute: id})
        except Exception:
            instance = None
            title = model._meta.verbose_name

        related = [
            (
                capfirst(model._meta.verbose_name_plural),
                reverse("history", args=(model._meta.db_table, attribute, id)),
            )
            for model, attribute in cfg.get("related", [])
        ]
    else:
        title = _("%(model)s with %(attribute)s=%(id)s") % {
            "model": model._meta.verbose_name_plural,
            "attribute": attribute,
            "id": id,
        }

    actions = LoggedAction.objects.for_model(model).with_data(**{attribute: id})

    return render(
        request,
        "history_modal.html",
        {
            "instance": instance,
            "title": title,
            "changes": changes(model, fields, actions),
            "related": related,
        },
    )
