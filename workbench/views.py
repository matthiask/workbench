from django.apps import apps
from django.contrib import messages
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.audit.models import LoggedAction
from workbench.contacts.models import (
    EmailAddress,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
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
            )
        ]
    else:
        messages.error(request, _("Search query missing."))

    return render(request, "search.html", {"query": q, "results": results})


def _projects_project_cfg(user):
    exclude = {"_code", "_fts"}
    related = []
    if user.features[FEATURES.CONTROLLING]:
        related = [(Offer, "project_id"), (Service, "project_id")]
    else:
        exclude |= {"flat_rate"}
    return {"exclude": exclude, "related": related}


def _logbook_entry_cfg(user):
    exclude = set()
    if not user.features[FEATURES.CONTROLLING]:
        exclude |= {"invoice_service", "archived_at"}
    return {"exclude": exclude}


def _offers_offer_cfg(user):
    exclude = {"_code"}
    if not user.features[FEATURES.CONTROLLING]:
        exclude |= {
            "subtotal",
            "discount",
            "liable_to_vat",
            "total_excl_tax",
            "tax_rate",
            "total",
            "show_service_details",
        }
    return {"exclude": exclude}


def _projects_service_cfg(user):
    exclude = {"position"}
    if not user.features[FEATURES.CONTROLLING]:
        exclude |= {
            "service_cost",
            "effort_type",
            "effort_rate",
            "effort_hours",
            "cost",
            "third_party_costs",
            "is_optional",
            "offer",
            "allow_logging",
        }
    if not user.features[FEATURES.GLASSFROG]:
        exclude |= {"role"}
    return {"exclude": exclude}


HISTORY = {
    "accounts_user": {"exclude": {"is_admin", "last_login", "password"}},
    "awt_employment": {"exclude": {"hourly_labor_costs", "green_hours_target"}},
    "contacts_person": {
        "exclude": {"_fts"},
        "related": [
            (PhoneNumber, "person_id"),
            (EmailAddress, "person_id"),
            (PostalAddress, "person_id"),
        ],
    },
    "invoices_invoice": {"exclude": {"_code", "_fts"}},
    "invoices_service": {"exclude": {"position"}},
    "logbook_loggedcost": _logbook_entry_cfg,
    "logbook_loggedhours": _logbook_entry_cfg,
    "offers_offer": _offers_offer_cfg,
    "projects_project": _projects_project_cfg,
    "projects_service": _projects_service_cfg,
}

DB_TABLE_TO_MODEL = {model._meta.db_table: model for model in apps.get_models()}


def history(request, db_table, attribute, id):
    try:
        model = DB_TABLE_TO_MODEL[db_table]
    except KeyError:
        raise Http404

    cfg = HISTORY.get(db_table, {})
    if callable(cfg):
        cfg = cfg(request.user)
    exclude = cfg.get("exclude", set())

    fields = [
        f
        for f in model._meta.get_fields()
        if hasattr(f, "attname") and not f.primary_key and f.name not in exclude
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
                model._meta.verbose_name_plural,
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

    actions = LoggedAction.objects.for_model_id(model, **{attribute: id})

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
