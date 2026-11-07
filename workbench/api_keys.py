"""Stable keys of choices for the API

Statuses and probabilities are stored as numbers which give them a natural
ordering, but they aren't nice in the API, they have keys here. Other
choices are stored as strings which are their keys. The API outputs and
accepts the keys (with a localized label next to them), ``/api/choices/``
lists them."""

from typing import Literal

from ninja import Router, Schema

from workbench.awt.models import Absence
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.offers.models import Offer
from workbench.projects.models import Project


# Which model field each set of keys belongs to, for the labels and the tests
FIELDS = {
    "deal_status": (Deal, "status"),
    "deal_probability": (Deal, "probability"),
    "offer_status": (Offer, "status"),
    "invoice_status": (Invoice, "status"),
    # Stored as their keys
    "invoice_type": (Invoice, "type"),
    "recurring_invoice_periodicity": (RecurringInvoice, "periodicity"),
    "absence_reason": (Absence, "reason"),
    "project_type": (Project, "type"),
}

KEYS = {
    "deal_status": {
        "open": Deal.OPEN,
        "accepted": Deal.ACCEPTED,
        "declined": Deal.DECLINED,
    },
    "deal_probability": {
        "unknown": Deal.UNKNOWN,
        "low": Deal.LOW,
        "normal": Deal.NORMAL,
        "high": Deal.HIGH,
    },
    "offer_status": {
        "in_preparation": Offer.IN_PREPARATION,
        "service_group": Offer.SERVICE_GROUP,
        "offered": Offer.OFFERED,
        "accepted": Offer.ACCEPTED,
        "declined": Offer.DECLINED,
        "discarded": Offer.DISCARDED,
    },
    "invoice_status": {
        "in_preparation": Invoice.IN_PREPARATION,
        "sent": Invoice.SENT,
        "paid": Invoice.PAID,
        "canceled": Invoice.CANCELED,
    },
}

KEYS |= {
    name: {value: value for value, _label in model._meta.get_field(field).choices}
    for name, (model, field) in FIELDS.items()
    if name not in KEYS
}

_VALUES = {
    name: {value: key for key, value in keys.items()} for name, keys in KEYS.items()
}

DealStatus = Literal[tuple(KEYS["deal_status"])]
DealProbability = Literal[tuple(KEYS["deal_probability"])]
OfferStatus = Literal[tuple(KEYS["offer_status"])]
InvoiceStatus = Literal[tuple(KEYS["invoice_status"])]
InvoiceType = Literal[tuple(KEYS["invoice_type"])]
Periodicity = Literal[tuple(KEYS["recurring_invoice_periodicity"])]
AbsenceReason = Literal[tuple(KEYS["absence_reason"])]
ProjectType = Literal[tuple(KEYS["project_type"])]


def key(name, value):
    """The stable key of a stored value, e.g. ``key("offer_status", 20)``"""
    return _VALUES[name][value]


router = Router(tags=["choices"])


class Choice(Schema):
    key: str
    label: str


@router.get("/choices/", response=dict[str, list[Choice]])
def choices(request):
    """The keys of statuses and probabilities with their labels, in their
    natural order"""
    return {
        name: [
            {"key": key(name, value), "label": str(label)}
            for value, label in model._meta.get_field(field).choices
        ]
        for name, (model, field) in FIELDS.items()
    }
