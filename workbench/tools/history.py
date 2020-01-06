import re
from collections import namedtuple
from functools import lru_cache

from django.db import models
from django.http import Http404
from django.urls import reverse
from django.utils import dateparse
from django.utils.html import conditional_escape, format_html, mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.models import Absence, Employment
from workbench.contacts.models import (
    EmailAddress,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.credit_control.models import CreditEntry
from workbench.expenses.models import ExpenseReport
from workbench.invoices.models import (
    Invoice,
    RecurringInvoice,
    Service as InvoiceService,
)
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service as ProjectService
from workbench.tools.formats import local_date_format


Change = namedtuple("Change", "changes version")


def boolean_formatter(value):
    if value in {True, "t"}:
        return _("yes")
    elif value in {False, "f"}:
        return _("no")
    return value


def default_if_none(value, default):
    return default if value is None else value


def date_formatter(value):
    if value is None:
        return _("<no value>")
    dt = dateparse.parse_datetime(value) or dateparse.parse_date(value)
    return local_date_format(dt) if dt else value


@lru_cache()
def formatter(field):
    """
    Returns a formatter for the passed model field instance
    """
    if field.choices:
        choices = {str(key): value for key, value in field.flatchoices}
        return lambda value: default_if_none(choices.get(value, value), "<empty>")

    if field.related_model:
        model = field.related_model
        queryset = model._default_manager.all()

        def _fn(value):
            if value is None:
                return _("<no value>")

            try:
                pretty = str(queryset.get(pk=value))
            except model.DoesNotExist:
                pretty = _("Deleted %s instance") % model._meta.verbose_name

            if model in HISTORY:
                return format_html(
                    '<a href="{}" data-toggle="ajaxmodal">{}</a>',
                    reverse("history", args=(model._meta.db_table, "id", value)),
                    pretty,
                )
            else:
                return pretty

        return _fn

    if isinstance(field, (models.BooleanField, models.NullBooleanField)):
        return boolean_formatter

    if isinstance(field, models.DateField):
        return date_formatter

    return lambda value: default_if_none(value, _("<no value>"))


def changes(model, fields, actions):
    changes = []

    if not actions:
        return changes

    users = {str(u.pk): u.get_full_name() for u in User.objects.all()}
    for action in actions:
        match = re.search(r"^user-([0-9]+)-", action.user_name)
        if match:
            pk = match.groups()[0]
            action.pretty_user_name = users.get(pk) or action.user_name
        else:
            action.pretty_user_name = action.user_name

    for action in actions:
        if action.action == "I":
            values = action.row_data
            version_changes = [
                mark_safe(
                    _("Initial value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(
                            formatter(f)(values.get(f.attname))
                        ),
                    }
                )
                for f in fields
                if not (f.many_to_many or f.one_to_many)  # Avoid those relation types.
            ]

        elif action.action == "U":
            values = action.changed_fields or {}
            version_changes = [
                mark_safe(
                    _("New value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(
                            formatter(f)(values.get(f.attname))
                        ),
                    }
                )
                for f in fields
                if f.attname in values
            ]

        else:  # Deletion or truncation
            values = action.row_data
            version_changes = [
                mark_safe(
                    _("Final value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(
                            formatter(f)(values.get(f.attname))
                        ),
                    }
                )
                for f in fields
                if not (f.many_to_many or f.one_to_many)  # Avoid those relation types.
            ]

        if version_changes:
            changes.append(Change(changes=version_changes, version=action))

    return changes


def _credit_control_creditentry_cfg(user):
    if not user.features[FEATURES.CONTROLLING]:
        raise Http404
    return {
        "fields": {
            "ledger",
            "reference_number",
            "value_date",
            "total",
            "payment_notice",
            "invoice",
            "notes",
        }
    }


def _invoices_invoice_cfg(user):
    if not user.features[FEATURES.CONTROLLING]:
        raise Http404
    return {
        "fields": {
            "customer",
            "contact",
            "project",
            "invoiced_on",
            "due_on",
            "closed_on",
            "last_reminded_on",
            "title",
            "description",
            "owned_by",
            "created_at",
            "status",
            "type",
            "down_payment_applied_to",
            "down_payment_total",
            "third_party_costs",
            "postal_address",
            "payment_notice",
        }
        | WITH_TOTAL,
        "related": [(CreditEntry, "invoice_id")],
    }


def _invoices_service_cfg(user):
    if not user.features[FEATURES.CONTROLLING]:
        raise Http404
    return {
        "fields": {
            "created_at",
            "title",
            "description",
            "service_hours",
            "service_cost",
            "effort_type",
            "effort_hours",
            "effort_rate",
            "cost",
            "third_party_costs",
            "invoice",
            "project_service",
        }
    }


def _invoices_recurringinvoice_cfg(user):
    if not user.features[FEATURES.CONTROLLING]:
        raise Http404
    return {
        "fields": {
            "customer",
            "contact",
            "title",
            "description",
            "owned_by",
            "created_at",
            "third_party_costs",
            "postal_address",
            "starts_on",
            "ends_on",
            "periodicity",
            "next_period_starts_on",
        }
        | WITH_TOTAL
    }


def _logbook_loggedcost_cfg(user):
    fields = {
        "service",
        "created_at",
        "created_by",
        "rendered_on",
        "rendered_by",
        "cost",
        "third_party_costs",
        "description",
        "are_expenses",
        "expense_report",
    }
    if user.features[FEATURES.CONTROLLING]:
        fields |= {"invoice_service", "archived_at"}
    if user.features[FEATURES.FOREIGN_CURRENCIES]:
        fields |= {"expense_currency", "expense_cost"}
    return {"fields": fields}


def _logbook_loggedhours_cfg(user):
    fields = {
        "service",
        "created_at",
        "created_by",
        "rendered_on",
        "rendered_by",
        "hours",
        "description",
    }
    if user.features[FEATURES.CONTROLLING]:
        fields |= {"invoice_service", "archived_at"}
    return {"fields": fields}


def _offers_offer_cfg(user):
    fields = {
        "created_at",
        "project",
        "offered_on",
        "closed_on",
        "title",
        "description",
        "owned_by",
        "status",
        "postal_address",
    }
    if user.features[FEATURES.CONTROLLING]:
        fields |= WITH_TOTAL
    return {"fields": fields}


def _projects_project_cfg(user):
    fields = {
        "customer",
        "contact",
        "title",
        "description",
        "owned_by",
        "type",
        "created_at",
        "closed_on",
    }
    related = []
    if user.features[FEATURES.CONTROLLING]:
        related = [(Offer, "project_id"), (ProjectService, "project_id")]
        fields |= {"flat_rate"}
    return {"fields": fields, "related": related}


def _projects_service_cfg(user):
    fields = {
        "created_at",
        "title",
        "description",
        "service_hours",
        "project",
        "offer",
        "allow_logging",
        "is_optional",
    }
    if user.features[FEATURES.CONTROLLING]:
        fields |= {
            "service_cost",
            "effort_type",
            "effort_rate",
            "effort_hours",
            "cost",
            "third_party_costs",
        }
    if user.features[FEATURES.GLASSFROG]:
        fields |= {"role"}
    return {"fields": fields}


WITH_TOTAL = {
    "subtotal",
    "discount",
    "liable_to_vat",
    "total_excl_tax",
    "tax_rate",
    "total",
    "show_service_details",
}

HISTORY = {
    User: {
        "fields": {
            "email",
            "is_active",
            "_short_name",
            "_full_name",
            "enforce_same_week_logging",
            "working_time_model",
        },
        "related": [(Employment, "user_id"), (Absence, "user_id")],
    },
    Absence: {
        "fields": {"user", "starts_on", "days", "description", "reason", "is_vacation"}
    },
    CreditEntry: _credit_control_creditentry_cfg,
    ExpenseReport: {
        "fields": {"created_at", "created_by", "closed_on", "owned_by", "total"},
        "related": [(LoggedCost, "expense_report_id")],
    },
    Employment: {
        "fields": {
            "user",
            "date_from",
            "date_until",
            "percentage",
            "vacation_weeks",
            "notes",
        }
    },
    EmailAddress: {"fields": {"person", "type", "email"}},
    PhoneNumber: {"fields": {"person", "type", "phone_number"}},
    PostalAddress: {
        "fields": {
            "person",
            "type",
            "street",
            "house_number",
            "address_suffix",
            "postal_code",
            "city",
            "country",
            "postal_address_override",
        }
    },
    Organization: {
        "fields": {
            "name",
            "is_private_person",
            "notes",
            "primary_contact",
            "default_billing_address",
        },
        "related": [(Person, "organization_id")],
    },
    Person: {
        "fields": {
            "is_archived",
            "given_name",
            "family_name",
            "address",
            "address_on_first_name_terms",
            "salutation",
            "date_of_birth",
            "notes",
            "organization",
            "primary_contact",
        },
        "related": [
            (PhoneNumber, "person_id"),
            (EmailAddress, "person_id"),
            (PostalAddress, "person_id"),
        ],
    },
    Invoice: _invoices_invoice_cfg,
    InvoiceService: _invoices_service_cfg,
    RecurringInvoice: _invoices_recurringinvoice_cfg,
    LoggedCost: _logbook_loggedcost_cfg,
    LoggedHours: _logbook_loggedhours_cfg,
    Offer: _offers_offer_cfg,
    Project: _projects_project_cfg,
    ProjectService: _projects_service_cfg,
}
