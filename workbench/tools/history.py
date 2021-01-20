from collections import namedtuple
from decimal import Decimal

from django.db import models
from django.http import Http404
from django.urls import reverse
from django.utils import dateparse
from django.utils.html import conditional_escape, format_html, mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import Team, User
from workbench.awt.models import Absence, Employment, Year
from workbench.contacts.models import (
    EmailAddress,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.credit_control.models import CreditEntry
from workbench.deals.models import Deal, Value, ValueType
from workbench.expenses.models import ExpenseReport
from workbench.invoices.models import (
    Invoice,
    RecurringInvoice,
    Service as InvoiceService,
)
from workbench.logbook.models import Break, LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.planning.models import PlannedWork, PlanningRequest
from workbench.projects.models import Campaign, Project, Service as ProjectService
from workbench.reporting.models import CostCenter
from workbench.tools.formats import local_date_format


# This is an object which __contains__ everything
EVERYTHING = type(str("c"), (), {"__contains__": lambda *a: True})()

Change = namedtuple("Change", "changes created_at pretty_user_name values version")


def default_if_none(value, default):
    return default if value is None else value


class Prettifier:
    def __init__(self):
        self._flatchoices = {}
        self._prettified_instances = {}

    def handle_bool(self, values, field):
        value = values.get(field.attname)
        if value in {True, "t"}:
            values[field.attname] = True
            return _("yes")
        elif value in {False, "f"}:
            values[field.attname] = False
            return _("no")
        elif value is None:
            values[field.attname] = None
            return _("<no value>")
        return value

    def handle_choice(self, values, field):
        if field not in self._flatchoices:
            self._flatchoices[field] = {
                str(key): (key, value) for key, value in field.flatchoices
            }
        value = values.get(field.attname)
        if value in self._flatchoices[field]:
            key, value = self._flatchoices[field][value]
            values[field.attname] = key

        return default_if_none(value, _("<no value>"))

    def handle_date(self, values, field):
        value = values.get(field.attname)
        if value is None:
            return _("<no value>")
        dt = dateparse.parse_datetime(value) or dateparse.parse_date(value)
        if dt:
            values[field.attname] = dt
            return local_date_format(dt)
        return value

    def handle_decimal(self, values, field):
        value = values.get(field.attname)
        if value:
            value = Decimal(value)
            values[field.attname] = value
        return default_if_none(value, _("<no value>"))

    def handle_related_model(self, values, field):
        value = values.get(field.attname)
        if value is None:
            return _("<no value>")

        model = field.related_model
        key = (model, value)
        if key in self._prettified_instances:
            values[field.attname] = self._prettified_instances[key][0]
            return self._prettified_instances[key][1]

        queryset = model._default_manager.all()

        instance = None
        try:
            instance = queryset.get(pk=value)
            pretty = str(instance)
        except model.DoesNotExist:
            pretty = _("Deleted %s instance") % model._meta.verbose_name
        else:
            values[field.attname] = instance

        if model in HISTORY:
            pretty = format_html(
                '<a href="{}" data-toggle="ajaxmodal">{}</a>',
                reverse("history", args=(model._meta.db_table, "id", value)),
                pretty,
            )

        self._prettified_instances[key] = (instance, pretty)
        return pretty

    def format(self, values, field):
        value = values.get(field.attname)

        if field.choices:
            return self.handle_choice(values, field)

        if field.related_model:
            return self.handle_related_model(values, field)

        if isinstance(field, (models.BooleanField, models.NullBooleanField)):
            return self.handle_bool(values, field)

        if isinstance(field, models.DateField):
            return self.handle_date(values, field)

        if isinstance(field, models.DecimalField):
            return self.handle_decimal(values, field)

        return default_if_none(value, _("<no value>"))


def changes(model, fields, actions):
    changes = []

    if not actions:
        return changes

    users = {u.pk: u.get_full_name() for u in User.objects.all()}
    users[0] = _("<anonymous>")
    fields = [
        f
        for f in model._meta.get_fields()
        if hasattr(f, "attname") and not f.primary_key and f.name in fields
    ]

    prettifier = Prettifier()

    for action in actions:
        if action.action == "I":
            values = action.row_data
            version_changes = [
                mark_safe(
                    _("Initial value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(prettifier.format(values, f)),
                    }
                )
                for f in fields
                if f.attname in values
            ]

        elif action.action == "U":
            values = action.changed_fields or {}
            version_changes = [
                mark_safe(
                    _("New value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(prettifier.format(values, f)),
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
                        "current": conditional_escape(prettifier.format(values, f)),
                    }
                )
                for f in fields
                if f.attname in values
            ]

        if version_changes:
            changes.append(
                Change(
                    changes=version_changes,
                    created_at=action.created_at,
                    pretty_user_name=users.get(action.user_id) or action.user_name,
                    values={
                        f.attname: values.get(f.attname)
                        for f in fields
                        if f.attname in values
                    },
                    version=action,
                )
            )

    return changes


def _accounts_user_cfg(user):
    fields = {
        "email",
        "is_active",
        "is_admin",
        "_short_name",
        "_full_name",
        "enforce_same_week_logging",
        "language",
        "working_time_model",
        "planning_hours_per_day",
        "person",
    }
    related = [(Employment, "user_id"), (Absence, "user_id")]
    if user.features[FEATURES.PLANNING]:
        related.extend([(PlannedWork, "user_id")])
    return {"fields": fields, "related": related}


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


def _deals_deal_cfg(user):
    if not user.features[FEATURES.DEALS]:
        raise Http404
    return {
        "fields": EVERYTHING,
        "related": [(Value, "deal_id")],
    }


def _deals_value_cfg(user):
    if not user.features[FEATURES.DEALS]:
        raise Http404
    return {"fields": EVERYTHING}


def _deals_valuetype_cfg(user):
    if not user.features[FEATURES.DEALS]:
        raise Http404
    return {"fields": EVERYTHING}


def _invoices_invoice_cfg(user):
    if not user.features[FEATURES.CONTROLLING]:
        raise Http404
    return {
        "fields": EVERYTHING,
        "related": [(CreditEntry, "invoice_id")],
    }


def _invoices_service_cfg(user):
    if not user.features[FEATURES.CONTROLLING]:
        raise Http404
    return {"fields": EVERYTHING}


def _invoices_recurringinvoice_cfg(user):
    if not user.features[FEATURES.CONTROLLING]:
        raise Http404
    return {"fields": EVERYTHING}


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


def _projects_campaign_cfg(user):
    if not user.features[FEATURES.CAMPAIGNS]:
        raise Http404
    return {
        "fields": {"customer", "title", "description", "owned_by"},
        "related": [(Project, "campaign_id")],
    }


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
        related.extend([(Offer, "project_id"), (ProjectService, "project_id")])
        fields |= {"flat_rate"}
    if user.features[FEATURES.CAMPAIGNS]:
        fields |= {"campaign"}
    if user.features[FEATURES.LABOR_COSTS]:
        fields |= {"cost_center"}
    if user.features[FEATURES.PLANNING]:
        related.extend([(PlanningRequest, "project_id"), (PlannedWork, "project_id")])
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


def _reporting_costcenter_cfg(user):
    if not user.features[FEATURES.LABOR_COSTS]:
        raise Http404
    return {"fields": {"title"}}


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
    User: _accounts_user_cfg,
    Team: {"fields": EVERYTHING},
    Absence: {"fields": EVERYTHING},
    Year: {"fields": EVERYTHING},
    CreditEntry: _credit_control_creditentry_cfg,
    Deal: _deals_deal_cfg,
    Value: _deals_value_cfg,
    ValueType: _deals_valuetype_cfg,
    ExpenseReport: {
        "fields": EVERYTHING,
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
    EmailAddress: {"fields": EVERYTHING},
    PhoneNumber: {"fields": EVERYTHING},
    PostalAddress: {"fields": EVERYTHING},
    Organization: {"fields": EVERYTHING, "related": [(Person, "organization_id")]},
    Person: {
        "fields": EVERYTHING,
        "related": [
            (PhoneNumber, "person_id"),
            (EmailAddress, "person_id"),
            (PostalAddress, "person_id"),
        ],
    },
    Invoice: _invoices_invoice_cfg,
    InvoiceService: _invoices_service_cfg,
    RecurringInvoice: _invoices_recurringinvoice_cfg,
    Break: {"fields": EVERYTHING},
    LoggedCost: _logbook_loggedcost_cfg,
    LoggedHours: _logbook_loggedhours_cfg,
    Offer: _offers_offer_cfg,
    PlanningRequest: {"fields": EVERYTHING, "related": [(PlannedWork, "request_id")]},
    PlannedWork: {"fields": EVERYTHING},
    Campaign: _projects_campaign_cfg,
    Project: _projects_project_cfg,
    ProjectService: _projects_service_cfg,
    CostCenter: _reporting_costcenter_cfg,
}
