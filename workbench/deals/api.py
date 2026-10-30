import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.contacts.models import Person
from workbench.deals.forms import DealForm
from workbench.deals.models import AttributeGroup, Deal, ValueType


# Same as in the web interface
router = Router(auth=user_auth(feature=FEATURES.DEALS), tags=["deals"])

STATUSES = {"open": Deal.OPEN, "accepted": Deal.ACCEPTED, "declined": Deal.DECLINED}
# Unknown isn't offered in the web interface
PROBABILITIES = {
    "low": Deal.LOW,
    "normal": Deal.NORMAL,
    "high": Deal.HIGH,
}


class ValueOut(Schema):
    type: str
    value: Decimal


class DealOut(Schema):
    id: int
    code: str
    url: str
    title: str
    description: str
    customer: str
    owned_by: str
    status: str
    probability: str
    decision_expected_on: dt.date | None
    value: Decimal
    values: list[ValueOut]
    closed_on: dt.date | None
    closing_type: str | None
    closing_notice: str
    contributors: list[str]
    related_offers: list[str]


def deal_out(deal, request):
    return {
        "id": deal.id,
        "code": deal.code,
        "url": request.build_absolute_uri(deal.get_absolute_url()),
        "title": deal.title,
        "description": deal.description,
        "customer": deal.customer.name,
        "owned_by": deal.owned_by.get_short_name(),
        "status": deal.get_status_display(),
        "probability": deal.get_probability_display(),
        "decision_expected_on": deal.decision_expected_on,
        "value": deal.value,
        "values": [
            {"type": value.type.title, "value": value.value}
            for value in deal.values.all()
        ],
        "closed_on": deal.closed_on,
        "closing_type": deal.closing_type.title if deal.closing_type else None,
        "closing_notice": deal.closing_notice,
        "contributors": [user.get_short_name() for user in deal.contributors.all()],
        "related_offers": [offer.code for offer in deal.related_offers.all()],
    }


class DealFilter(Schema):
    q: str = ""
    status: Literal["open", "accepted", "declined"] | None = None
    customer: int | None = None
    owned_by: str | None = None


@router.get("/deals/", response=list[DealOut])
def deal_list(request, filters: Query[DealFilter]):
    """Deals, open deals with the earliest expected decision first, at most 200"""
    deals = Deal.objects.select_related(
        "customer", "owned_by", "closing_type"
    ).prefetch_related("values__type", "contributors", "related_offers__project")
    if filters.status:
        deals = deals.filter(status=STATUSES[filters.status])
    if filters.customer:
        deals = deals.filter(customer=filters.customer)
    if filters.owned_by:
        deals = deals.filter(owned_by___short_name__iexact=filters.owned_by)
    if filters.q:
        deals = deals.search(filters.q)
    deals = deals.order_by("status", "decision_expected_on", "-pk")
    return [deal_out(deal, request) for deal in deals[:200]]


@router.get("/deals/{deal_id}/", response=DealOut)
def deal_detail(request, deal_id: int):
    return deal_out(
        get_object_or_404(
            Deal.objects.select_related("customer", "owned_by", "closing_type"),
            pk=deal_id,
        ),
        request,
    )


class DealIn(Schema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    customer: int | None = Field(
        default=None,
        description="ID of the customer organization, defaults to the contact's"
        " organization.",
    )
    contact: int | None = Field(
        default=None, description="ID of the contact person at the customer."
    )
    owned_by: str | None = Field(
        default=None,
        description="Short name of the person responsible, defaults to the"
        " authenticated user.",
    )
    probability: Literal["low", "normal", "high"]
    decision_expected_on: dt.date | None = None
    values: dict[str, Decimal] = Field(
        default={}, description="Values by the title of their value type."
    )
    attributes: dict[str, str] = Field(
        default={},
        description="Attributes by the title of their group; required groups"
        " must be given.",
    )


class DealCreated(DealOut):
    id: int | None
    code: str | None
    url: str | None


def _choices(objects):
    return ", ".join(repr(str(obj.title)) for obj in objects)


@router.post("/deals/", response=DealCreated)
def deal_create(request, data: DealIn, *, dry_run: bool = False):
    """Create a deal, validated like in the web interface

    You are its main driving force. Warnings of the web interface are errors
    here; nothing is saved if anything is invalid or with ``dry_run``."""
    errors = []

    def error(loc, msg):
        errors.append({"loc": ["body", "data", *loc], "msg": msg})

    owned_by = request.user
    if data.owned_by is not None:
        owned_by = User.objects.filter(
            is_active=True, _short_name__iexact=data.owned_by
        ).first()
        if not owned_by:
            error(["owned_by"], _("Unknown or inactive user %r.") % data.owned_by)

    customer = data.customer
    if customer is None and data.contact:
        contact = Person.objects.filter(pk=data.contact).first()
        customer = contact.organization_id if contact else None

    form_data = {
        "title": data.title,
        "description": data.description,
        "customer": customer or "",
        "contact": data.contact or "",
        "owned_by": owned_by.pk if owned_by else "",
        "probability": PROBABILITIES[data.probability],
        "decision_expected_on": data.decision_expected_on or "",
        f"user_{request.user.pk}_contribution": 100,
    }
    fields = {}

    value_types = list(ValueType.objects.filter(is_archived=False))
    by_title = {vt.title.casefold(): vt for vt in value_types}
    for title, value in data.values.items():
        if vt := by_title.get(title.casefold()):
            form_data[f"value_{vt.id}"] = value
            fields[f"value_{vt.id}"] = ["values", vt.title]
        else:
            error(
                ["values", title],
                _("Unknown value type. Choices: %s") % _choices(value_types),
            )

    groups = list(
        AttributeGroup.objects.filter(is_archived=False).prefetch_related("attributes")
    )
    by_title = {group.title.casefold(): group for group in groups}
    for title, attribute_title in data.attributes.items():
        if not (group := by_title.get(title.casefold())):
            error(
                ["attributes", title],
                _("Unknown attribute group. Choices: %s") % _choices(groups),
            )
            continue
        attributes = [a for a in group.attributes.all() if not a.is_archived]
        attribute = next(
            (a for a in attributes if a.title.casefold() == attribute_title.casefold()),
            None,
        )
        if attribute:
            form_data[f"attribute_{group.id}"] = attribute.pk
        else:
            error(
                ["attributes", group.title],
                _("Unknown attribute. Choices: %s") % _choices(attributes),
            )
    for group in groups:
        fields[f"attribute_{group.id}"] = ["attributes", group.title]
        if group.is_required and f"attribute_{group.id}" not in form_data:
            error(
                ["attributes", group.title],
                _("This field is required. Choices: %s")
                % _choices(a for a in group.attributes.all() if not a.is_archived),
            )

    if errors:
        raise ValidationError(errors)

    form = DealForm(form_data, request=request)
    if not form.is_valid():
        raise ValidationError(
            [
                {
                    "loc": ["body", "data"]
                    + ([] if field == "__all__" else fields.get(field, [field])),
                    "msg": message,
                }
                for field, messages in form.errors.items()
                for message in messages
            ]
            + [
                {"loc": ["body", "data"], "msg": str(warning)}
                for warning in form.warnings.values()
            ]
        )

    with transaction.atomic():
        deal = form.save()
        result = deal_out(deal, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "code": None, "url": None}
    return result
