import datetime as dt

from django.apps import apps
from django.contrib import messages
from django.db import connections
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
from workbench.logbook.models import LoggedHours
from workbench.offers.models import Offer
from workbench.planning.models import PlanningRequest
from workbench.projects.models import Campaign, Project
from workbench.tools.history import HISTORY, changes
from workbench.tools.validation import in_days


def _needs_action(user):
    rows = []
    if user.features[FEATURES.DEALS]:
        rows.append(
            {
                "type": "deals",
                "verbose_name_plural": Deal._meta.verbose_name_plural,
                "url": Deal.urls["list"],
                "objects": Deal.objects.maybe_actionable(user=user),
            }
        )
    if user.features[FEATURES.CONTROLLING]:
        rows.append(
            {
                "type": "offers",
                "verbose_name_plural": Offer._meta.verbose_name_plural,
                "url": Offer.urls["list"],
                "objects": Offer.objects.maybe_actionable(user=user),
            }
        )
    if user.features[FEATURES.PLANNING]:
        rows.append(
            {
                "type": "planninrequests",
                "verbose_name_plural": PlanningRequest._meta.verbose_name_plural,
                "url": user.urls["planning"],
                "objects": PlanningRequest.objects.maybe_actionable(user=user),
            }
        )

    return [row for row in rows if row["objects"]]


def _todays_hours(user):
    return (
        LoggedHours.objects.filter(rendered_by=user, rendered_on=dt.date.today())
        .select_related("service__project__owned_by", "rendered_by", "timestamp")
        .order_by("-created_at")[:15]
    )


def _all_users_hours():
    return (
        LoggedHours.objects.filter(rendered_on__gte=in_days(-7))
        .select_related("service__project__owned_by", "rendered_by", "timestamp")
        .order_by("-created_at")[:20]
    )


def _birthdays():
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """
SELECT id, given_name, family_name, date_of_birth, is_active_user FROM (
    SELECT
        p.id,
        given_name,
        family_name,
        date_of_birth,
        u.is_active AS is_active_user,
        (current_date - date_of_birth) % 365.24 AS diff
    FROM contacts_person p
    LEFT OUTER JOIN accounts_user u ON p.id=u.person_id
    WHERE date_of_birth is not null AND is_archived=FALSE
) AS subquery
WHERE diff < 7 or diff > 350
ORDER BY (diff + 180) % 365 DESC
            """
        )
        return [
            {
                "id": row[0],
                "given_name": row[1],
                "family_name": row[2],
                "date_of_birth": row[3],
                "is_active_user": row[4],
            }
            for row in cursor
        ]


def _in_preparation(user):
    invoices = Invoice.objects.filter(
        owned_by=user, status=Invoice.IN_PREPARATION
    ).select_related("project", "owned_by")
    offers = Offer.objects.filter(
        owned_by=user, status=Offer.IN_PREPARATION
    ).select_related("project", "owned_by")

    return {
        key: value
        for key, value in [("invoices", invoices), ("offers", offers)]
        if value
    }


def start(request):
    request.user.take_a_break_warning(request=request)

    return render(
        request,
        "start.html",
        {
            "needs_action": _needs_action(request.user),
            "todays_hours": _todays_hours(request.user),
            "all_users_hours": _all_users_hours(),
            "birthdays": _birthdays(),
            "in_preparation": _in_preparation(request.user),
        },
    )


def search(request):
    results = []
    if q := request.GET.get("q", ""):
        sources = [
            Project.objects.select_related("owned_by"),
        ]
        if request.user.features[FEATURES.CAMPAIGNS]:
            sources.append(Campaign.objects.select_related("owned_by"))
        sources.extend(
            [
                Organization.objects.active(),
                Person.objects.active().select_related("organization"),
            ]
        )
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
            "model": capfirst(model._meta.verbose_name_plural),
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
