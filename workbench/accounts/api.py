import datetime as dt
from decimal import Decimal

from ninja import Router, Schema

from workbench.accounts.features import FEATURES
from workbench.deals.api import DealOut, deal_out
from workbench.deals.models import Deal
from workbench.invoices.api import InvoiceOut, invoice_out
from workbench.invoices.models import Invoice
from workbench.offers.api import OfferOut, offer_out
from workbench.offers.models import Offer
from workbench.planning.models import PlannedWork
from workbench.projects.api import ProjectOut, project_out
from workbench.projects.models import Project
from workbench.tools.validation import monday


router = Router(tags=["accounts"])


class MeOut(Schema):
    id: int
    short_name: str
    full_name: str
    email: str
    url: str


@router.get("/me/", response=MeOut)
def me(request):
    """The authenticated user"""
    user = request.user
    return {
        "id": user.id,
        "short_name": user.get_short_name(),
        "full_name": user.get_full_name(),
        "email": user.email,
        "url": request.build_absolute_uri("/"),
    }


class PlannedWorkThisWeek(Schema):
    title: str
    project: ProjectOut
    hours: Decimal
    is_provisional: bool


class Overview(Schema):
    week: dt.date
    projects: list[ProjectOut]
    planned_work: list[PlannedWorkThisWeek]
    offers: list[OfferOut] | None
    invoices: list[InvoiceOut] | None
    deals: list[DealOut] | None


@router.get("/me/overview/", response=Overview)
def overview(request):
    """What's on the authenticated user's plate

    Offers, invoices and deals which may need action are ``null`` if the user
    hasn't got the feature required to see them."""
    user = request.user
    week = monday()
    features = user.features
    return {
        "week": week,
        "projects": [
            project_out(project, request)
            for project in Project.objects
            .open()
            .filter(owned_by=user)
            .select_related("customer", "owned_by")
        ],
        "planned_work": [
            {
                "title": pw.title,
                "project": project_out(pw.project, request),
                "hours": (pw.planned_hours / len(pw.weeks)).quantize(Decimal("0.1")),
                "is_provisional": pw.is_provisional,
            }
            for pw in PlannedWork.objects.filter(
                user=user, weeks__contains=[week]
            ).select_related("project__customer", "project__owned_by")
        ],
        "offers": [
            offer_out(offer, list(offer.services.all()), request)
            for offer in Offer.objects.maybe_actionable(user=user).prefetch_related(
                "services"
            )
        ]
        if features[FEATURES.CONTROLLING]
        else None,
        "invoices": [
            invoice_out(invoice, request)
            for invoice in Invoice.objects.maybe_actionable(user=user).select_related(
                "customer"
            )
        ]
        if features[FEATURES.CONTROLLING]
        else None,
        "deals": [
            deal_out(deal, request)
            for deal in Deal.objects.maybe_actionable(user=user).select_related(
                "customer", "owned_by", "closing_type"
            )
        ]
        if features[FEATURES.DEALS]
        else None,
    }
