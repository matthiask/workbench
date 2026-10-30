import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db.models import Q
from ninja import Field, Query, Router, Schema
from ninja.pagination import paginate

from workbench.accounts.features import FEATURES
from workbench.accounts.models import Team, User
from workbench.deals.api import DealOut, deal_out, with_related
from workbench.deals.models import Deal
from workbench.invoices.api import InvoiceOut, invoice_out
from workbench.invoices.models import Invoice
from workbench.offers.api import OfferOut, offer_out
from workbench.offers.models import Offer
from workbench.planning.models import PlannedWork
from workbench.projects.api import ProjectOut, project_out
from workbench.projects.models import Project
from workbench.tools.api import Serialized
from workbench.tools.validation import monday


router = Router(tags=["accounts"])


class MeOut(Schema):
    id: int
    short_name: str
    full_name: str
    email: str
    url: str
    access: Literal["read", "write"] = Field(
        description="Whether the API token only allows reading; sessions can"
        " always read and write."
    )


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
        "access": token.access
        if (token := getattr(request, "api_token", None))
        else "write",
    }


class UserOut(Schema):
    id: int
    url: str
    short_name: str
    full_name: str
    email: str
    is_active: bool
    teams: list[str]


class UserFilter(Schema):
    q: str = ""
    include_inactive: bool = False


@router.get("/users/", response=list[UserOut])
@paginate
def user_list(request, filters: Query[UserFilter]):
    """Search users by name, short name or email address, e.g. for the short
    names which identify them in other APIs"""
    users = User.objects.prefetch_related("teams").order_by("_full_name", "pk")
    if not filters.include_inactive:
        users = users.filter(is_active=True)
    for term in filters.q.split():
        users = users.filter(
            Q(_full_name__icontains=term)
            | Q(_short_name__icontains=term)
            | Q(email__icontains=term)
        )
    return Serialized(
        users,
        lambda user: {
            "id": user.id,
            "url": request.build_absolute_uri(user.get_absolute_url()),
            "short_name": user.get_short_name(),
            "full_name": user.get_full_name(),
            "email": user.email,
            "is_active": user.is_active,
            "teams": [team.name for team in user.teams.all()],
        },
    )


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
            for deal in with_related(Deal.objects.maybe_actionable(user=user))
        ]
        if features[FEATURES.DEALS]
        else None,
    }


class TeamOut(Schema):
    id: int
    url: str
    name: str
    members: list[str]


class TeamFilter(Schema):
    q: str = ""


@router.get("/teams/", response=list[TeamOut])
@paginate
def team_list(request, filters: Query[TeamFilter]):
    """Teams with the short names of their active members, e.g. for the
    ``team`` filter of reports"""
    teams = Team.objects.prefetch_related("members").order_by("name", "pk")
    if filters.q:
        teams = teams.filter(name__icontains=filters.q)
    return Serialized(
        teams,
        lambda team: {
            "id": team.id,
            "url": request.build_absolute_uri(team.get_absolute_url()),
            "name": team.name,
            "members": sorted(
                member.get_short_name()
                for member in team.members.all()
                if member.is_active
            ),
        },
    )
