import datetime as dt
from decimal import Decimal
from typing import Literal

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError, ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.accounts.forms import TeamForm
from workbench.accounts.models import APIToken, Team, User
from workbench.deals.api import DealOut, deal_out, with_related
from workbench.deals.models import Deal
from workbench.invoices.api import InvoiceOut, invoice_out
from workbench.invoices.models import Invoice
from workbench.offers.api import OfferOut, offer_out
from workbench.offers.models import Offer
from workbench.planning.models import PlannedWork
from workbench.projects.api import ProjectOut, project_out
from workbench.projects.models import Project
from workbench.tools.api import (
    DryRun,
    InputSchema,
    SearchQuery,
    Serialized,
    delete_with_form,
    patch_with_form,
)
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
    features: list[str] = Field(
        description="The features of the user, e.g. controlling, deals,"
        " bookkeeping or productivity; endpoints require the same features as"
        " the web interface."
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
        "features": sorted(
            name.lower()
            for name, feature in FEATURES.__members__.items()
            if user.features[feature]
        ),
    }


class UserOut(Schema):
    id: int
    url: str
    short_name: str
    full_name: str
    email: str
    is_active: bool
    teams: list[str]
    specialist_field: str | None
    value_type: str | None = Field(
        description="The value type of the specialist field, e.g. for splitting"
        " the value of work between value types by who did it."
    )


class UserFilter(Schema):
    q: SearchQuery = ""
    include_inactive: bool = Field(default=False, description="Also users who left.")


@router.get("/users/", response=list[UserOut])
@paginate
def user_list(request, filters: Query[UserFilter]):
    """Search users by name, short name or email address, e.g. for the short
    names which identify them in other APIs"""
    users = (
        User.objects
        .select_related("specialist_field__value_type")
        .prefetch_related("teams")
        .order_by("_full_name", "pk")
    )
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
            "specialist_field": field.name
            if (field := user.specialist_field)
            else None,
            "value_type": field.value_type.title
            if field and field.value_type
            else None,
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
            .select_related("customer", "contact", "owned_by")
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
            ).select_related(
                "project__customer", "project__contact", "project__owned_by"
            )
        ],
        "offers": [
            offer_out(offer, list(offer.services.all()), request)
            for offer in Offer.objects
            .maybe_actionable(user=user)
            .select_related("project__customer")
            .prefetch_related("services", "headings", "deals")
        ]
        if features[FEATURES.CONTROLLING]
        else None,
        "invoices": [
            invoice_out(invoice, request)
            for invoice in Invoice.objects.maybe_actionable(user=user).select_related(
                "customer", "project__customer"
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
    q: SearchQuery = ""


@router.get("/teams/", response=list[TeamOut])
@paginate
def team_list(request, filters: Query[TeamFilter]):
    """Teams with the short names of their active members, e.g. for the
    ``team`` filter of reports"""
    teams = Team.objects.prefetch_related("members").order_by("name", "pk")
    if filters.q:
        teams = teams.filter(name__icontains=filters.q)
    return Serialized(teams, lambda team: team_out(team, request))


def team_out(team, request):
    return {
        "id": team.id,
        "url": request.build_absolute_uri(team.get_absolute_url()),
        "name": team.name,
        "members": sorted(
            member.get_short_name() for member in team.members.all() if member.is_active
        ),
    }


def _team(value):
    """The team with this ID or name (case-insensitive)"""
    value = value.strip()
    teams = Team.objects.all()
    if value.isascii() and value.isdigit():
        return get_object_or_404(teams, pk=int(value))
    return get_object_or_404(teams, name__iexact=value)


class TeamIn(InputSchema):
    name: str
    members: list[str] = Field(description="Short names of active users.")


class TeamPatch(InputSchema):
    """Fields which aren't given are left alone"""

    name: str | None = None
    members: list[str] | None = Field(
        default=None,
        description="Replaces the members; short names of active users.",
    )
    add_members: list[str] = Field(
        default=[], description="Short names of active users."
    )
    remove_members: list[str] = Field(default=[], description="Short names.")


def _user_pks(short_names, field, errors, *, active_only=True):
    """The PKs of the users with these short names; like the form's choices
    only active ones (unless ``active_only=False``)"""
    pks = []
    for index, short_name in enumerate(short_names):
        users = User.objects.by_short_name(short_name)
        if user := (users.filter(is_active=True) if active_only else users).first():
            pks.append(user.pk)
        else:
            errors.append({
                "loc": ["body", "data", field, index],
                "msg": _("Unknown or inactive user %r.") % short_name,
            })
    return pks


def _save_team(request, team, values, *, dry_run):
    return patch_with_form(
        TeamForm,
        team,
        values,
        request,
        out=lambda team: team_out(team, request),
        dry_run=dry_run,
    )


@router.post("/teams/", response=TeamOut)
def team_create(request, data: TeamIn, *, dry_run: DryRun = False):
    """Create a team, e.g. for the ``team`` filter of reports and the
    planning; anyone may, like in the web interface"""
    errors = []
    members = _user_pks(data.members, "members", errors)
    if errors:
        raise ValidationError(errors)
    return _save_team(
        request, Team(), {"name": data.name, "members": members}, dry_run=dry_run
    )


@router.patch("/teams/{team_id}/", response=TeamOut)
def team_update(request, team_id: str, data: TeamPatch, *, dry_run: DryRun = False):
    """Rename a team (by ID or name) or change its members

    Like the web interface, which only shows active members, saving drops
    members who left."""
    team = _team(team_id)
    errors = []
    if data.members is not None:
        members = set(_user_pks(data.members, "members", errors))
    else:
        members = set(team.members.active().values_list("pk", flat=True))
    members |= set(_user_pks(data.add_members, "add_members", errors))
    members -= set(
        _user_pks(data.remove_members, "remove_members", errors, active_only=False)
    )
    if errors:
        raise ValidationError(errors)
    values = {"members": sorted(members)}
    if "name" in data.model_fields_set:
        values["name"] = data.name
    return _save_team(request, team, values, dry_run=dry_run)


@router.delete("/teams/{team_id}/", response=TeamOut)
def team_delete(request, team_id: str, *, dry_run: DryRun = False):
    """Delete a team (by ID or name) like in the web interface, its members
    stay; returns the deleted team"""
    team = _team(team_id)
    result = team_out(team, request)
    delete_with_form(team, request, loc=["path", "team_id"], dry_run=dry_run)
    return result


class APITokenOut(Schema):
    id: int
    title: str
    access: Literal["read", "write"]
    access_label: str
    created_at: dt.datetime
    last_used_at: dt.datetime | None
    expires_at: dt.datetime
    current: bool = Field(
        description="Whether this is the token which authenticated the request."
    )


def api_token_out(token, request):
    current = getattr(request, "api_token", None)
    return {
        "id": token.id,
        "title": token.title,
        "access": token.access,
        "access_label": token.get_access_display(),
        "created_at": token.created_at,
        "last_used_at": token.last_used_at,
        "expires_at": token.expires_at,
        "current": bool(current and current.pk == token.pk),
    }


@router.get("/tokens/", response=list[APITokenOut])
def api_token_list(request):
    """The authenticated user's API tokens which haven't expired yet"""
    return [
        api_token_out(token, request)
        for token in request.user.api_tokens.filter(expires_at__gt=timezone.now())
    ]


@router.delete(
    "/tokens/current/",
    response=APITokenOut,
    auth=user_auth(allow_read_only=True),
)
def api_token_delete_current(request):
    """Revoke the API token which authenticated the request, e.g. when logging
    out; read only tokens may do this too. Returns the deleted token."""
    if not (token := getattr(request, "api_token", None)):
        raise HttpError(422, _("This request wasn't authenticated with a token."))
    result = api_token_out(token, request)
    token.delete()
    return result


@router.delete(
    "/tokens/{token_id}/",
    response=APITokenOut,
    auth=user_auth(allow_read_only=True),
)
def api_token_delete(request, token_id: int):
    """Revoke one of the authenticated user's API tokens immediately, e.g.
    one which isn't needed anymore or has leaked

    Read only tokens may only revoke themselves. Returns the deleted token."""
    token = get_object_or_404(request.user.api_tokens, pk=token_id)
    current = getattr(request, "api_token", None)
    if current and current.access == APIToken.Access.READ and current.pk != token.pk:
        raise HttpError(403, _("This API token only allows reading, not changes."))
    result = api_token_out(token, request)
    token.delete()
    return result
