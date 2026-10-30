import datetime as dt
import html
from decimal import Decimal
from typing import Literal

from django.db import transaction
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.contacts.api import OrganizationOut, organization_out
from workbench.contacts.models import Person
from workbench.deals.forms import DealForm
from workbench.deals.models import AttributeGroup, Deal, ValueType
from workbench.deals.reporting import accepted_deals, deal_history, declined_deals
from workbench.tools.api import (
    Amount,
    DateRangeFilter,
    Serialized,
    UsersFilter,
    date_range,
    filter_date_range,
    filter_users,
    raise_form_errors,
)
from workbench.tools.formats import Z2
from workbench.tools.validation import monday


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
    customer: OrganizationOut
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
        "customer": organization_out(deal.customer, request),
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


class DealFilter(DateRangeFilter):
    q: str = ""
    status: Literal["open", "accepted", "declined"] | None = None
    customer: int | None = None
    owned_by: str | None = None


@router.get("/deals/", response=list[DealOut])
@paginate
def deal_list(request, filters: Query[DealFilter]):
    """Deals, open deals with the earliest expected decision first; the
    period filters the decision date (when the deal was closed, or is
    expected to be decided if it is still open)"""
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
    deals = filter_date_range(
        deals.annotate(decision_on=Coalesce("closed_on", "decision_expected_on")),
        filters,
        "decision_on",
    )
    deals = deals.order_by("status", "decision_expected_on", "-pk")
    return Serialized(deals, lambda deal: deal_out(deal, request))


class StatsFilter(DateRangeFilter, UsersFilter):
    pass


def _this_week():
    return [monday(), monday() + dt.timedelta(days=6)]


def _deal_summary(deal, request):
    return {
        "id": deal.id,
        "code": deal.code,
        "url": request.build_absolute_uri(deal.get_absolute_url()),
        "title": deal.title,
        "customer": organization_out(deal.customer, request),
        "owned_by": deal.owned_by.get_short_name(),
        "value": deal.value,
        "closed_on": deal.closed_on,
    }


class DealSummary(Schema):
    id: int
    code: str
    url: str
    title: str
    customer: OrganizationOut
    owned_by: str
    value: Amount
    closed_on: dt.date | None


class DeclinedDeal(DealSummary):
    closing_type: str
    closing_notice: str


class AcceptedByUser(Schema):
    user: str
    count: int
    sum: Amount


class AcceptedByValueType(Schema):
    type: str
    sum: Amount
    target: Amount | None
    median_age_days: int | None


class AcceptedByMonth(Schema):
    month: str
    sum: Amount
    values: dict[str, Amount]


class AcceptedDeals(Schema):
    count: int
    sum: Amount
    target: Amount
    median_age_days: int | None
    by_user: list[AcceptedByUser]
    by_value_type: list[AcceptedByValueType]
    by_month: list[AcceptedByMonth]
    deals: list[DealSummary]


class ClosingTypeTotal(Schema):
    count: int
    sum: Amount


class DeclinedDeals(Schema):
    count: int
    sum: Amount
    by_closing_type: dict[str, ClosingTypeTotal]
    deals: list[DeclinedDeal]


class DealStats(Schema):
    since: dt.date
    until: dt.date
    accepted: AcceptedDeals
    declined: DeclinedDeals


class DealChange(Schema):
    created_at: dt.datetime
    user: str
    deal: DealSummary | None
    changes: list[str]


class DealHistory(Schema):
    since: dt.date
    until: dt.date
    changes: list[DealChange]


@router.get("/deals/stats/", response=DealStats)
def deal_stats(request, filters: Query[StatsFilter]):
    """Deals accepted and declined in the period (this week by default), with
    accepted deals per user (split by contributions), month and value type,
    compared to the value types' weekly targets. Users filter the deals'
    owners. Ages are the days between creating and closing deals."""
    period = date_range(filters, default=_this_week())
    users = filter_users(filters)
    accepted = accepted_deals(period, users=users)
    declined = declined_deals(period).select_related("closing_type")
    if users is not None:
        declined = declined.filter(owned_by__in=users)

    by_closing_type = {}
    for deal in declined:
        row = by_closing_type.setdefault(
            str(deal.pretty_closing_type), {"count": 0, "sum": Z2}
        )
        row["count"] += 1
        row["sum"] += deal.value

    return {
        "since": period[0],
        "until": period[1],
        "accepted": {
            "count": accepted["count"],
            "sum": accepted["sum"],
            "target": accepted["target"],
            "median_age_days": accepted["median_age"],
            "by_user": [
                {
                    "user": row["user"].get_short_name(),
                    "count": row["count"],
                    "sum": row["sum"],
                }
                for row in accepted["by_user"]
            ],
            "by_value_type": [
                {
                    "type": row["type"].title,
                    "sum": row["sum"],
                    "target": row["target"],
                    "median_age_days": row["median_age"],
                }
                for row in accepted["by_valuetype"]
            ],
            "by_month": [
                {
                    "month": f"{row['month']:%Y-%m}",
                    "sum": row["sum"],
                    "values": {
                        value["type"].title: value["value"] for value in row["values"]
                    },
                }
                for row in accepted["by_month_and_valuetype"]
            ],
            "deals": [_deal_summary(deal, request) for deal in accepted["deals"]],
        },
        "declined": {
            "count": len(declined),
            "sum": sum((deal.value for deal in declined), Z2),
            "by_closing_type": by_closing_type,
            "deals": [
                _deal_summary(deal, request)
                | {
                    "closing_type": str(deal.pretty_closing_type),
                    "closing_notice": deal.closing_notice,
                }
                for deal in declined
            ],
        },
    }


@router.get("/deals/history/", response=DealHistory)
def deal_history_api(request, filters: Query[StatsFilter]):
    """Changes of deals in the period (this week by default), oldest first;
    users filter who made the changes"""
    period = date_range(filters, default=_this_week())
    changes = deal_history(period, users=filter_users(filters))
    deals = Deal.objects.select_related("customer", "owned_by").in_bulk({
        int(change.version.row_data["id"]) for change in changes
    })
    return {
        "since": period[0],
        "until": period[1],
        "changes": [
            {
                "created_at": timezone.localtime(change.created_at),
                "user": str(change.pretty_user_name),
                "deal": _deal_summary(deal, request)
                if (deal := deals.get(int(change.version.row_data["id"])))
                else None,
                "changes": [html.unescape(strip_tags(text)) for text in change.changes],
            }
            for change in changes
        ],
    }


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
        raise_form_errors(form, fields=fields)

    with transaction.atomic():
        deal = form.save()
        result = deal_out(deal, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "code": None, "url": None}
    return result
