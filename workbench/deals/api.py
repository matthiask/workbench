import datetime as dt
from decimal import Decimal
from typing import Literal

from django.shortcuts import get_object_or_404
from ninja import Query, Router, Schema

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.deals.models import Deal


# Same as in the web interface
router = Router(auth=user_auth(feature=FEATURES.DEALS), tags=["deals"])

STATUSES = {"open": Deal.OPEN, "accepted": Deal.ACCEPTED, "declined": Deal.DECLINED}


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


def _deal_out(deal, request):
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
    return [_deal_out(deal, request) for deal in deals[:200]]


@router.get("/deals/{deal_id}/", response=DealOut)
def deal_detail(request, deal_id: int):
    return _deal_out(
        get_object_or_404(
            Deal.objects.select_related("customer", "owned_by", "closing_type"),
            pk=deal_id,
        ),
        request,
    )
