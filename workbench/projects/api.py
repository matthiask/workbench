import datetime as dt
from collections import defaultdict
from decimal import Decimal
from itertools import islice
from typing import Literal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import (
    DecimalField,
    OuterRef,
    ProtectedError,
    Q,
    Subquery,
    Sum,
)
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError, ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.api_codes import by_id_or_code
from workbench.api_keys import (
    DealStatus,
    InvoiceStatus,
    InvoiceType,
    OfferStatus,
    ProjectType,
    key,
)
from workbench.contacts.api import (
    OrganizationOut,
    PersonSummary,
    organization_out,
    person_summary,
)
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import (
    Offer,
    offer_items,
    reorder_services,
    save_positions,
)
from workbench.planning.models import PlannedWork
from workbench.projects.forms import (
    BudgetTransferForm,
    CampaignDeleteForm,
    CampaignForm,
    ProjectedInvoicesProjectForm,
    ProjectForm,
    ReassignLogbookForm,
    ServiceForm,
    ServiceMergeForm,
    ServiceMoveForm,
)
from workbench.projects.models import (
    BudgetTransfer,
    Campaign,
    InternalType,
    Project,
    Service,
)
from workbench.reporting.models import CostCenter
from workbench.reporting.project_budget_statistics import project_budget_statistics
from workbench.reporting.squeeze import project_gross_margin
from workbench.services.models import ServiceType
from workbench.tools.api import (
    IGNORE_WARNINGS,
    Amount,
    DryRun,
    InputSchema,
    Number,
    OrganizationID,
    ProjectID,
    SearchQuery,
    Serialized,
    ShortName,
    active_user,
    delete_with_form,
    form_data,
    object_pk,
    patch_with_form,
    raise_form_errors,
    user_by_short_name,
    validate_form,
    without_query,
)
from workbench.tools.formats import Z1, Z2


router = Router(tags=["projects"])


class ProjectCustomer(Schema):
    id: int
    name: str


class ProjectSummary(Schema):
    id: int
    code: str
    title: str
    url: str
    customer: ProjectCustomer = Field(
        description="Part of the project's label; details are in the organization."
    )


class DealRef(Schema):
    id: int
    code: str
    url: str
    title: str
    status: DealStatus
    status_label: str


def deal_refs(deals, request):
    """Deals linked to an offer or project, None without the deals feature"""
    if not request.user.features[FEATURES.DEALS]:
        return None
    return [
        {
            "id": deal.id,
            "code": deal.code,
            "url": request.build_absolute_uri(deal.get_absolute_url()),
            "title": deal.title,
            "status": key("deal_status", deal.status),
            "status_label": deal.get_status_display(),
        }
        for deal in deals
    ]


def project_summary(project, request):
    return {
        "id": project.id,
        "code": project.code,
        "title": project.title,
        "url": request.build_absolute_uri(project.get_absolute_url()),
        "customer": {"id": project.customer.id, "name": project.customer.name},
    }


class CampaignSummary(Schema):
    id: int
    code: str
    title: str


class ProjectOut(Schema):
    id: int
    code: str
    url: str
    title: str
    description: str
    customer: OrganizationOut
    contact: PersonSummary | None
    owned_by: str
    type: ProjectType
    type_label: str
    campaign: CampaignSummary | None
    flat_rate: Amount | None
    budget_alert_at: Amount | None
    suppress_planning_update_mails: bool
    internal_type: str | None
    created_at: dt.datetime
    closed_on: dt.date | None


def project_out(project, request):
    return {
        "id": project.id,
        "code": project.code,
        "url": request.build_absolute_uri(project.get_absolute_url()),
        "title": project.title,
        "description": project.description,
        "customer": organization_out(project.customer, request),
        "contact": person_summary(project.contact, request)
        if project.contact
        else None,
        "owned_by": project.owned_by.get_short_name(),
        "type": project.type,
        "type_label": project.get_type_display(),
        "campaign": {
            "id": project.campaign.id,
            "code": project.campaign.code,
            "title": project.campaign.title,
        }
        if project.campaign
        else None,
        "internal_type": project.internal_type.name if project.internal_type else None,
        "flat_rate": project.flat_rate,
        "budget_alert_at": project.budget_alert_at,
        "suppress_planning_update_mails": project.suppress_planning_update_mails,
        "created_at": project.created_at,
        "closed_on": project.closed_on,
    }


class ProjectFilter(Schema):
    q: SearchQuery = ""
    customer: OrganizationID = None
    owned_by: ShortName = None
    include_closed: bool = Field(default=False, description="Also closed projects.")


class CampaignOut(Schema):
    id: int
    code: str
    url: str
    title: str
    description: str
    customer: OrganizationOut
    owned_by: str


class CampaignFilter(Schema):
    q: SearchQuery = ""
    customer: OrganizationID = None
    owned_by: ShortName = None
    include_closed: bool = Field(
        default=False, description="Also campaigns without open projects."
    )


@router.get(
    "/campaigns/",
    response=list[CampaignOut],
    auth=user_auth(feature=FEATURES.CAMPAIGNS),
)
@paginate
def campaign_list(request, filters: Query[CampaignFilter]):
    """Campaigns group projects, those with open projects by default, newest
    first; the planning export takes their ID"""
    campaigns = Campaign.objects.select_related("customer", "owned_by")
    if not filters.include_closed:
        campaigns = campaigns.open()
    if filters.customer:
        campaigns = campaigns.filter(customer=filters.customer)
    if filters.owned_by:
        campaigns = campaigns.filter(
            owned_by=user_by_short_name(filters.owned_by, param="owned_by")
        )
    if filters.q:
        campaigns = campaigns.search(filters.q)
    return Serialized(
        campaigns.order_by("-pk"), lambda campaign: campaign_out(campaign, request)
    )


def campaign_out(campaign, request):
    return {
        "id": campaign.id,
        "code": campaign.code,
        "url": request.build_absolute_uri(campaign.get_absolute_url()),
        "title": campaign.title,
        "description": campaign.description,
        "customer": organization_out(campaign.customer, request),
        "owned_by": campaign.owned_by.get_short_name(),
    }


class CampaignIn(InputSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    customer: int = Field(description="Organization ID.")
    owned_by: str | None = Field(
        default=None, description="Short name, defaults to the current user."
    )


class CampaignCreated(CampaignOut):
    id: int | None
    code: str | None
    url: str | None


@router.post(
    "/campaigns/",
    response=CampaignCreated,
    auth=user_auth(feature=FEATURES.CAMPAIGNS),
)
def campaign_create(
    request,
    data: CampaignIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create a campaign, validated like in the web interface; nothing is
    saved if anything is invalid or with ``dry_run``"""
    owned_by = request.user
    if data.owned_by is not None:
        owned_by = (
            User.objects.by_short_name(data.owned_by).filter(is_active=True).first()
        )
        if not owned_by:
            raise ValidationError([
                {
                    "loc": ["body", "data", "owned_by"],
                    "msg": _("Unknown or inactive user %r.") % data.owned_by,
                }
            ])
    form = CampaignForm(
        {
            "title": data.title,
            "description": data.description,
            "customer": data.customer,
            "owned_by": owned_by.pk,
        },
        request=without_query(request),
    )
    validate_form(form, ignore_warnings=ignore_warnings)

    with transaction.atomic():
        campaign = form.save()
        result = campaign_out(campaign, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "code": None, "url": None}
    return result


class CampaignPatch(InputSchema):
    """Fields which aren't given are left alone"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    customer: int | None = Field(default=None, description="Organization ID.")
    owned_by: str | None = Field(default=None, description="Short name.")


@router.patch(
    "/campaigns/{campaign_id}/",
    response=CampaignOut,
    auth=user_auth(feature=FEATURES.CAMPAIGNS),
)
def campaign_update(
    request,
    campaign_id: int,
    data: CampaignPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change a campaign, validated like in the web interface; nothing is
    saved if anything is invalid or with ``dry_run``"""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    return patch_with_form(
        CampaignForm,
        campaign,
        data,
        without_query(request),
        out=lambda campaign: campaign_out(campaign, request),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map={"owned_by": active_user},
    )


@router.delete(
    "/campaigns/{campaign_id}/",
    response=CampaignOut,
    auth=user_auth(feature=FEATURES.CAMPAIGNS),
)
def campaign_delete(
    request,
    campaign_id: int,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Delete a campaign like in the web interface; its projects stay and
    are released (warning ``release-projects`` unless ignored). Returns the
    deleted campaign."""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    result = campaign_out(campaign, request)
    delete_with_form(
        campaign,
        without_query(request),
        loc=["path", "campaign_id"],
        delete_form_class=CampaignDeleteForm,
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
    )
    return result


class InternalTypeOut(Schema):
    id: int
    name: str
    description: str
    percentage: Decimal
    is_outreach: bool


@router.get("/projects/internal-types/", response=list[InternalTypeOut])
@paginate
def internal_type_list(request):
    """The internal types of internal projects; ``internal_type`` of
    projects takes their name or ID"""
    return Serialized(
        InternalType.objects.order_by("ordering", "pk"),
        lambda internal_type: {
            "id": internal_type.id,
            "name": internal_type.name,
            "description": internal_type.description,
            "percentage": internal_type.percentage,
            "is_outreach": internal_type.is_outreach,
        },
    )


@router.get("/projects/", response=list[ProjectOut])
@paginate
def project_list(request, filters: Query[ProjectFilter]):
    """Search projects, open projects only by default, newest first"""
    projects = Project.objects.select_related(
        "customer", "contact", "owned_by", "internal_type", "campaign"
    ).order_by("-pk")
    if not filters.include_closed:
        projects = projects.open()
    if filters.customer:
        projects = projects.filter(customer=filters.customer)
    if filters.owned_by:
        projects = projects.filter(
            owned_by=user_by_short_name(filters.owned_by, param="owned_by")
        )
    if q := filters.q:
        projects = projects.search(q)
    return Serialized(projects, lambda project: project_out(project, request))


class StatsFilter(Schema):
    ids: list[int] = Field(default=[], description="IDs of projects.")
    open: bool = Field(default=False, description="All open projects.")
    closed_since: dt.date | None = Field(
        default=None, description="Projects closed on or after this date."
    )


class HoursStats(Schema):
    offered: Decimal
    logged: Decimal
    logged_rate_undefined: Decimal
    planned: Decimal


class AmountStats(Schema):
    sold: Decimal
    invoiced: Decimal
    effort_cost: Decimal
    cost: Decimal
    third_party_costs: Decimal
    not_invoiced: Decimal


class GrossMarginStats(Schema):
    gross_margin: Decimal
    rate: Decimal
    offered: Decimal
    projected: Decimal
    invoiced: Decimal


class ServiceStats(Schema):
    id: int
    title: str
    offer: str | None
    offer_status: OfferStatus | None
    effort_type: str
    effort_rate: Decimal | None
    service_hours: Decimal
    service_cost: Decimal
    is_optional: bool


class LoggedHoursStats(Schema):
    service: int
    user: str
    hours: Decimal


class PlannedHoursStats(Schema):
    user: str
    planned_hours: Decimal
    is_provisional: bool


class InvoiceStats(Schema):
    id: int
    code: str
    title: str
    type: InvoiceType
    status: InvoiceStatus
    invoiced_on: dt.date | None
    total_excl_tax: Decimal
    third_party_costs: Decimal | None


class ProjectStats(Schema):
    project: ProjectOut
    hours: HoursStats
    amounts: AmountStats
    gross_margin: GrossMarginStats
    services: list[ServiceStats]
    logged_hours: list[LoggedHoursStats]
    planned_hours: list[PlannedHoursStats]
    invoices: list[InvoiceStats]


@router.get(
    "/projects/stats/",
    response=list[ProjectStats],
    auth=user_auth(feature=FEATURES.CONTROLLING),
)
def project_stats(request, filters: Query[StatsFilter]):
    """Hours, amounts and gross margins of the selected projects

    Selects the projects given by ``ids``, all open projects with ``open``
    and projects closed on or after ``closed_since``. People are identified
    by their short name."""
    q = Q(pk__in=filters.ids) if filters.ids else Q()
    if filters.open:
        q |= Q(closed_on__isnull=True)
    if filters.closed_since:
        q |= Q(closed_on__gte=filters.closed_since)
    if not q:
        raise HttpError(400, _("Select projects using ids, open or closed_since."))

    projects = list(
        Project.objects
        .filter(q)
        .select_related("customer", "contact", "owned_by", "internal_type", "campaign")
        .order_by("pk")
    )
    budget = {
        row["project"].id: row
        for row in project_budget_statistics(projects)["statistics"]
    }

    user_ids = set()
    logged_hours = defaultdict(list)
    for row in (
        LoggedHours.objects
        .filter(service__project__in=projects)
        .order_by()
        .values("service__project", "service", "rendered_by")
        .annotate(hours=Sum("hours"))
        .order_by("service__project", "service", "rendered_by")
    ):
        user_ids.add(row["rendered_by"])
        logged_hours[row["service__project"]].append(row)

    planned_hours = defaultdict(list)
    for row in (
        PlannedWork.objects
        .filter(project__in=projects)
        .order_by()
        .values("project", "user", "is_provisional")
        .annotate(planned_hours=Sum("planned_hours"))
        .order_by("project", "user", "is_provisional")
    ):
        user_ids.add(row["user"])
        planned_hours[row["project"]].append(row)

    short_names = {
        pk: user.get_short_name() for pk, user in User.objects.in_bulk(user_ids).items()
    }

    services = defaultdict(list)
    for project in projects:
        for service in project.services.select_related("offer__project"):
            services[project.id].append(service)

    invoices = defaultdict(list)
    for invoice in (
        Invoice.objects
        .filter(project__in=projects)
        .exclude(status=Invoice.IN_PREPARATION)
        .select_related("project")
        .order_by("invoiced_on", "pk")
    ):
        invoices[invoice.project_id].append(invoice)

    def project_stats(project):
        b = budget[project.id]
        gm = project_gross_margin(project)
        return {
            "project": project_out(project, request),
            "hours": {
                "offered": b["service_hours"],
                "logged": b["hours"],
                "logged_rate_undefined": b["effort_hours_with_rate_undefined"],
                "planned": sum(
                    (row["planned_hours"] for row in planned_hours[project.id]),
                    Z1,
                ),
            },
            "amounts": {
                key: b[field].quantize(Z2)
                for key, field in [
                    ("sold", "sold"),
                    ("invoiced", "invoiced"),
                    ("effort_cost", "effort_cost"),
                    ("cost", "cost"),
                    ("third_party_costs", "third_party_costs"),
                    ("not_invoiced", "delta"),
                ]
            },
            "gross_margin": {
                key: gm[key].quantize(Z2)
                for key in ["gross_margin", "rate", "offered", "projected", "invoiced"]
            },
            "services": [
                {
                    "id": service.id,
                    "title": service.title,
                    "offer": service.offer.code if service.offer else None,
                    "offer_status": key("offer_status", service.offer.status)
                    if service.offer
                    else None,
                    "effort_type": service.effort_type,
                    "effort_rate": service.effort_rate,
                    "service_hours": service.service_hours,
                    "service_cost": service.service_cost,
                    "is_optional": service.is_optional,
                }
                for service in services[project.id]
            ],
            "logged_hours": [
                {
                    "service": row["service"],
                    "user": short_names[row["rendered_by"]],
                    "hours": row["hours"],
                }
                for row in logged_hours[project.id]
            ],
            "planned_hours": [
                {
                    "user": short_names[row["user"]],
                    "planned_hours": row["planned_hours"],
                    "is_provisional": row["is_provisional"],
                }
                for row in planned_hours[project.id]
            ],
            "invoices": [
                {
                    "id": invoice.id,
                    "code": invoice.code,
                    "title": invoice.title,
                    "type": invoice.type,
                    "status": key("invoice_status", invoice.status),
                    "invoiced_on": invoice.invoiced_on,
                    "total_excl_tax": invoice.total_excl_tax,
                    "third_party_costs": invoice.third_party_costs,
                }
                for invoice in invoices[project.id]
            ],
        }

    return [project_stats(project) for project in projects]


# Budget transfers ############################################################


class BudgetTransferOut(Schema):
    id: int | None = Field(description="Null with dry_run when creating.")
    url: str | None
    from_project: ProjectSummary
    to_project: ProjectSummary | None = Field(
        description="Null while the budget is only reserved."
    )
    is_reserved: bool
    title: str
    amount: Amount
    notes: str
    created_at: dt.datetime
    created_by: str


def budget_transfer_out(transfer, request):
    return {
        "id": transfer.id,
        "url": request.build_absolute_uri(transfer.get_absolute_url()),
        "from_project": project_summary(transfer.from_project, request),
        "to_project": project_summary(transfer.to_project, request)
        if transfer.to_project
        else None,
        "is_reserved": transfer.is_reserved,
        "title": transfer.title,
        "amount": transfer.amount,
        "notes": transfer.notes,
        "created_at": transfer.created_at,
        "created_by": transfer.created_by.get_short_name(),
    }


def _budget_transfers():
    return BudgetTransfer.objects.select_related(
        "from_project__customer", "to_project__customer", "created_by"
    ).order_by("-created_at", "-pk")


def _project_budget_transfers(project):
    return _budget_transfers().filter(Q(from_project=project) | Q(to_project=project))


def _budget_transfer_saved(transfer, request, *, dry_run):
    """The saved transfer, without ID and URL if it's going to be rolled back"""
    result = budget_transfer_out(_budget_transfers().get(pk=transfer.pk), request)
    if dry_run:
        result |= {"id": None, "url": None}
    return result


BUDGET_TRANSFER_FORM = BudgetTransferForm.__wrapped__


class BudgetTransferFields(InputSchema):
    to_project: int | str | None = Field(
        default=None,
        description="ID or code of the project which does the work, null"
        " only reserves the budget (it leaves the source project anyway).",
    )
    notes: str | None = None


class BudgetTransferCreate(BudgetTransferFields):
    title: str = Field(min_length=1, max_length=200)
    amount: Number = Field(
        description="Part of the total invoiced on the project; more than its"
        " gross margin warns (budget-transfer-too-large), more than its"
        " accepted offers too (budget-transfer-beyond-offers)."
    )


class BudgetTransferPatch(BudgetTransferFields):
    """Fields which aren't given are left alone; the source project can't
    be changed"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    amount: Number | None = None


BUDGET_TRANSFER_FIELDS = {"to_project": object_pk(Project.objects.all())}


@router.get(
    "/projects/{project_id}/budget-transfers/",
    response=list[BudgetTransferOut],
    auth=user_auth(feature=FEATURES.CONTROLLING),
)
def budget_transfer_list(request, project_id: str):
    """The budget transfers from and to a project (by ID or code), newest
    first; see ``budget_adjustment`` of the project for their net effect"""
    project = by_id_or_code(Project.objects.all(), project_id)
    return [
        budget_transfer_out(transfer, request)
        for transfer in _project_budget_transfers(project)
    ]


@router.post(
    "/projects/{project_id}/budget-transfers/",
    response=BudgetTransferOut,
    auth=user_auth(feature=FEATURES.CONTROLLING),
)
def budget_transfer_create(
    request,
    project_id: str,
    data: BudgetTransferCreate,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Move budget invoiced on this project (by ID or code) to the project
    which does the work, or reserve it for later, validated like in the web
    interface. Only money moves, the hours stay where they were logged."""
    project = by_id_or_code(Project.objects.all(), project_id)
    return patch_with_form(
        BUDGET_TRANSFER_FORM,
        BudgetTransfer(from_project=project),
        data.model_dump(),
        request,
        out=lambda transfer: _budget_transfer_saved(transfer, request, dry_run=dry_run),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map=BUDGET_TRANSFER_FIELDS,
    )


@router.get(
    "/budget-transfers/{int:transfer_id}/",
    response=BudgetTransferOut,
    auth=user_auth(feature=FEATURES.CONTROLLING),
)
def budget_transfer_detail(request, transfer_id: int):
    return budget_transfer_out(
        get_object_or_404(_budget_transfers(), pk=transfer_id), request
    )


@router.patch(
    "/budget-transfers/{int:transfer_id}/",
    response=BudgetTransferOut,
    auth=user_auth(feature=FEATURES.CONTROLLING),
)
def budget_transfer_update(
    request,
    transfer_id: int,
    data: BudgetTransferPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change a budget transfer, e.g. name the project which does the work
    of a reserved one; validated like in the web interface"""
    return patch_with_form(
        BUDGET_TRANSFER_FORM,
        get_object_or_404(BudgetTransfer, pk=transfer_id),
        data,
        request,
        out=lambda transfer: _budget_transfer_saved(transfer, request, dry_run=False),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map=BUDGET_TRANSFER_FIELDS,
    )


@router.delete(
    "/budget-transfers/{int:transfer_id}/",
    response=BudgetTransferOut,
    auth=user_auth(feature=FEATURES.CONTROLLING),
)
def budget_transfer_delete(request, transfer_id: int, *, dry_run: DryRun = False):
    """Delete a budget transfer, the budget goes back to its source project.
    Returns the deleted transfer."""
    transfer = get_object_or_404(_budget_transfers(), pk=transfer_id)
    result = budget_transfer_out(transfer, request)
    delete_with_form(transfer, request, loc=["path", "transfer_id"], dry_run=dry_run)
    return result


def project_budget_transfers(project, request):
    """The budget transfers of the project and their net effect on its
    figures, ``None`` without the controlling feature"""
    if not request.user.features[FEATURES.CONTROLLING]:
        return {"budget_transfers": None, "budget_adjustment": None}
    return {
        "budget_transfers": [
            budget_transfer_out(transfer, request)
            for transfer in _project_budget_transfers(project)
        ],
        "budget_adjustment": BudgetTransfer.objects.adjustments(projects=[project])[
            project.id
        ],
    }


# End of budget transfers #####################################################


class ProjectDetail(ProjectOut):
    cost_center: str | None = Field(description="Title of the cost center.")
    deals: list[DealRef] | None = Field(
        description="Deals linked to the project, directly or through one of"
        " its offers; null without the deals feature."
    )
    budget_transfers: list[BudgetTransferOut] | None = Field(
        description="Budget transfers from and to the project; null without"
        " the controlling feature."
    )
    budget_adjustment: Amount | None = Field(
        description="Net budget transfers (in minus out), included in the sold"
        " amount and the gross margin of the project's statistics; null"
        " without the controlling feature."
    )


def project_detail_out(project, request):
    return (
        project_out(project, request)
        | {
            "cost_center": project.cost_center.title if project.cost_center else None,
            "deals": deal_refs(
                Deal.objects
                .filter(
                    Q(related_projects=project) | Q(related_offers__project=project)
                )
                .distinct()
                .order_by("-pk"),
                request,
            ),
        }
        | project_budget_transfers(project, request)
    )


@router.get("/projects/{project_id}/", response=ProjectDetail)
def project_detail(request, project_id: str):
    """A project by its ID or code (2026-0042)"""
    project = by_id_or_code(
        Project.objects.select_related(
            "customer",
            "contact",
            "owned_by",
            "internal_type",
            "campaign",
            "cost_center",
        ),
        project_id,
    )
    return project_detail_out(project, request)


class ProjectIn(InputSchema):
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
    type: Literal["order", "maintenance", "internal"] = "order"
    internal_type: str | None = Field(
        default=None,
        description="Name or ID of the internal type, required for internal"
        " projects if the installation uses internal types.",
    )
    owned_by: str | None = Field(
        default=None,
        description="Short name of the person responsible, defaults to the"
        " authenticated user.",
    )


class ProjectCreated(ProjectOut):
    id: int | None
    url: str | None


def _internal_type(name):
    """The internal type's ID for the project form"""
    if not name:
        return ""
    types = {it.name.casefold(): it for it in InternalType.objects.all()}
    if internal_type := types.get(name.casefold()):
        return internal_type.pk
    # Names first, then IDs (only ASCII digits)
    if (
        name.isascii()
        and name.isdigit()
        and (
            internal_type := next(
                (it for it in types.values() if it.pk == int(name)), None
            )
        )
    ):
        return internal_type.pk
    raise ValidationError([
        {
            "loc": ["body", "data", "internal_type"],
            "msg": _("Unknown internal type %(name)r, use one of %(types)s.")
            % {
                "name": name,
                "types": ", ".join(sorted(it.name for it in types.values())),
            },
        }
    ])


@router.post("/projects/", response=ProjectCreated)
def project_create(
    request,
    data: ProjectIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create a project, validated like in the web interface

    Warnings of the web interface are errors here unless ignored by their
    code; nothing is saved if anything is invalid or with ``dry_run``."""
    owned_by = request.user
    if data.owned_by is not None:
        owned_by = (
            User.objects.by_short_name(data.owned_by).filter(is_active=True).first()
        )
        if not owned_by:
            raise ValidationError([
                {
                    "loc": ["body", "data", "owned_by"],
                    "msg": _("Unknown or inactive user %r.") % data.owned_by,
                }
            ])

    form = ProjectForm(
        {
            "title": data.title,
            "description": data.description,
            # The form uses the contact's organization if empty
            "customer": "" if data.customer is None else data.customer,
            "contact": data.contact or "",
            "type": data.type,
            "internal_type": _internal_type(data.internal_type),
            "owned_by": owned_by.pk,
        },
        request=request,
    )
    validate_form(form, ignore_warnings=ignore_warnings)

    with transaction.atomic():
        project = form.save()
        result = project_out(project, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
    return result


class ProjectPatch(InputSchema):
    """Fields which aren't given are left alone"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    customer: int | None = Field(default=None, description="Organization ID.")
    contact: int | None = Field(
        default=None, description="ID of the contact person, null removes it."
    )
    type: Literal["order", "maintenance", "internal"] | None = None
    internal_type: str | None = Field(
        default=None,
        description="Name or ID of the internal type. Projects which aren't internal"
        " anymore lose it.",
    )
    owned_by: str | None = Field(default=None, description="Short name.")
    campaign: int | None = Field(
        default=None, description="ID of the campaign, null removes it."
    )
    cost_center: str | None = Field(
        default=None,
        description="Title or ID of the cost center, null removes it (labor"
        " costs feature).",
    )
    flat_rate: Number | None = Field(
        default=None,
        description="Hourly rate of all services, null removes it. Overwrites"
        " the rates of the services which haven't been invoiced (warning"
        " flat-rate-but-already-services).",
    )
    budget_alert_at: Number | None = Field(
        default=None,
        description="Send a mail when the logged cost reaches this amount,"
        " null removes it.",
    )
    suppress_planning_update_mails: bool | None = Field(
        default=None,
        description="Suppress the planning update mails of this project for everyone.",
    )
    closed_on: dt.date | None = Field(
        default=None, description="Closes the project, null reopens it."
    )
    delete_planned_work: bool | None = Field(
        default=None,
        description="Required when closing a project whose offers in"
        " preparation (which are discarded) have planned work: delete it or"
        " keep it. Ignored otherwise.",
    )


def _cost_center(value):
    """Converter for ``patch_with_form()``: the cost center by its title
    (case-insensitive) or ID"""
    cost_centers = list(CostCenter.objects.all())
    for cost_center in cost_centers:
        if cost_center.title.casefold() == value.casefold():
            return cost_center.pk
    for cost_center in cost_centers:
        if value.isascii() and value.isdigit() and cost_center.pk == int(value):
            return cost_center.pk
    raise DjangoValidationError(
        _("Unknown cost center %(name)r, use one of %(cost_centers)s.")
        % {
            "name": value,
            "cost_centers": ", ".join(cc.title for cc in cost_centers) or "-",
        }
    )


class SettledOfferOut(Schema):
    id: int
    code: str
    url: str
    title: str
    status: OfferStatus
    status_label: str


class ProjectUpdateOut(ProjectDetail):
    settled_offers: list[SettledOfferOut] = Field(
        description="Offers in preparation which closing the project just"
        " discarded, or declined if they have been sent before."
    )


def settled_offer_out(offer, request):
    return {
        "id": offer.id,
        "code": offer.code,
        "url": request.build_absolute_uri(offer.get_absolute_url()),
        "title": offer.title,
        "status": key("offer_status", offer.status),
        "status_label": offer.get_status_display(),
    }


@router.patch("/projects/{project_id}/", response=ProjectUpdateOut)
def project_update(
    request,
    project_id: int,
    data: ProjectPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change or close a project, validated like in the web interface

    Closing a project discards its offers in preparation (or declines them
    if they have been sent before), ``settled_offers`` lists them. Warnings
    of the web interface are errors here unless ignored by their code;
    nothing is saved if anything is invalid or with ``dry_run``."""
    project = get_object_or_404(Project, pk=project_id)
    in_preparation = list(
        project.offers.filter(status=Offer.IN_PREPARATION).values_list("pk", flat=True)
    )

    def out(project):
        settled = (
            project.offers
            .filter(pk__in=in_preparation)
            .exclude(status=Offer.IN_PREPARATION)
            .select_related("project", "owned_by")
            .order_by("pk")
        )
        return project_detail_out(project, request) | {
            "settled_offers": [settled_offer_out(offer, request) for offer in settled]
        }

    patch = data.model_dump(exclude_unset=True)
    # Projects which aren't internal anymore lose their internal type
    if patch.get("type") not in {None, Project.INTERNAL}:
        patch.setdefault("internal_type", None)
    return patch_with_form(
        ProjectForm,
        project,
        patch,
        request,
        out=out,
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map={
            "owned_by": active_user,
            "internal_type": _internal_type,
            "campaign": object_pk(Campaign.objects.all()),
            "cost_center": _cost_center,
            "delete_planned_work": int,
        },
        # The form reads initial values from the web interface's parameters
        form_kwargs={"request": without_query(request)},
    )


@router.delete("/projects/{project_id}/", response=ProjectDetail)
def project_delete(request, project_id: str, *, dry_run: DryRun = False):
    """Delete a project (by ID or code) like in the web interface, e.g. one
    created by mistake; refused if offers, invoices or logged hours or costs
    depend on it. Its services, planned work and projected invoices are
    deleted too. Returns the deleted project."""
    project = by_id_or_code(
        Project.objects.select_related(
            "customer",
            "contact",
            "owned_by",
            "internal_type",
            "campaign",
            "cost_center",
        ),
        project_id,
    )
    result = project_detail_out(project, request)
    delete_with_form(project, request, loc=["path", "project_id"], dry_run=dry_run)
    return result


class ProjectedInvoiceIn(InputSchema):
    id: int | None = Field(
        default=None,
        description="ID of a projected invoice of the project to change. Without"
        " it, a projected invoice with the same date which isn't listed"
        " otherwise is changed, else a new one is created.",
    )
    invoiced_on: dt.date
    gross_margin: Number = Field(
        description="Invoice total excl. tax minus third party costs incl. tax."
    )
    description: str = Field(default="", max_length=200)


class ProjectedInvoicesIn(InputSchema):
    projected_invoices: list[ProjectedInvoiceIn] = Field(
        description="All projected invoices of the project, the ones not listed"
        " are deleted."
    )


class ProjectedInvoiceItem(Schema):
    id: int | None = Field(description="Null for new ones with dry_run.")
    invoiced_on: dt.date
    gross_margin: Amount
    description: str


class ProjectedInvoicesOut(Schema):
    project: ProjectSummary
    projected_invoices: list[ProjectedInvoiceItem]
    total: Amount


def _match_projected_invoices(items, existing):
    """The existing projected invoice (by PK) each item changes: by its ID,
    or the first one with the same date which isn't listed otherwise"""
    loc = ["body", "data", "projected_invoices"]
    matched, errors = {}, []
    for index, item in enumerate(items):
        if item.id is None:
            continue
        if item.id not in existing:
            msg = _("Projected invoice %r doesn't belong to this project.") % item.id
        elif item.id in matched.values():
            msg = _("Projected invoice %r is listed twice.") % item.id
        else:
            matched[index] = item.id
            continue
        errors.append({"loc": [*loc, index, "id"], "msg": msg})
    if errors:
        raise ValidationError(errors)
    for index, item in enumerate(items):
        if item.id is None and (
            pk := next(
                (
                    pk
                    for pk, pi in existing.items()
                    if pk not in matched.values() and pi.invoiced_on == item.invoiced_on
                ),
                None,
            )
        ):
            matched[index] = pk
    return matched


@router.put(
    "/projects/{project_id}/projected-invoices/",
    response=ProjectedInvoicesOut,
    auth=user_auth(feature=FEATURES.PROJECTED_GROSS_MARGIN),
)
def project_projected_invoices(
    request, project_id: str, data: ProjectedInvoicesIn, *, dry_run: DryRun = False
):
    """Replace the projected invoices of a project (by ID or code) like the
    web interface's form: projected gross margin, third party costs are not
    included

    Projected invoices which aren't listed are deleted. New ones and changed
    dates must be after the freeze date, closed projects get no new ones."""
    project = by_id_or_code(Project.objects.select_related("customer"), project_id)
    form_kwargs = {"instance": project, "request": request}
    formset = ProjectedInvoicesProjectForm(**form_kwargs).formsets["projected_invoices"]
    forms = {form.instance.pk: form for form in formset.initial_forms}
    matched = _match_projected_invoices(
        data.projected_invoices, {pk: form.instance for pk, form in forms.items()}
    )

    # The formset's data: the existing projected invoices with their current
    # values (deleted unless matched), the changes and the new ones on top
    values = {
        f"{formset.prefix}-TOTAL_FORMS": len(forms)
        + len(data.projected_invoices)
        - len(matched),
        f"{formset.prefix}-INITIAL_FORMS": len(forms),
        f"{formset.prefix}-MIN_NUM_FORMS": 0,
        f"{formset.prefix}-MAX_NUM_FORMS": 1000,
    }
    for form in forms.values():
        for name in form.fields:
            value = form[name].value()
            values[form.add_prefix(name)] = "" if value is None else value
        values[form.add_prefix("DELETE")] = (
            "" if form.instance.pk in matched.values() else "on"
        )
    indexes = {
        form.instance.pk: index for index, form in enumerate(formset.initial_forms)
    }
    request_index = {}  # Index of the form -> index in the request
    new = len(forms)
    for index, item in enumerate(data.projected_invoices):
        if index in matched:
            form_index = indexes[matched[index]]
        else:
            form_index, new = new, new + 1
        request_index[form_index] = index
        for name, value in [
            ("invoiced_on", item.invoiced_on.isoformat()),
            ("gross_margin", item.gross_margin),
            ("description", item.description),
        ]:
            values[f"{formset.prefix}-{form_index}-{name}"] = value

    form = ProjectedInvoicesProjectForm(values, **form_kwargs)
    if not form.is_valid():
        formset = form.formsets["projected_invoices"]
        loc = ["body", "data", "projected_invoices"]
        raise ValidationError(
            [{"loc": loc, "msg": message} for message in formset.non_form_errors()]
            + [
                {
                    "loc": [*loc, request_index[index]]
                    + ([] if field == "__all__" else [field]),
                    "msg": message,
                }
                for index, subform in enumerate(formset.forms)
                if index in request_index
                for field, messages in subform.errors.items()
                for message in messages
            ]
        )

    with transaction.atomic():
        form.save()
        created = {obj.pk for obj in form.formsets["projected_invoices"].new_objects}
        projected_invoices = list(
            project.projected_invoices.order_by("invoiced_on", "pk")
        )
        result = {
            "project": project_summary(project, request),
            "projected_invoices": [
                {
                    "id": None if dry_run and pi.pk in created else pi.pk,
                    "invoiced_on": pi.invoiced_on,
                    "gross_margin": pi.gross_margin,
                    "description": pi.description,
                }
                for pi in projected_invoices
            ],
            "total": sum((pi.gross_margin for pi in projected_invoices), Z2),
        }
        if dry_run:
            transaction.set_rollback(True)
    return result


class ServiceOut(Schema):
    id: int | None = Field(description="Null for services created with dry_run.")
    url: str | None
    project: ProjectSummary
    offer_id: int | None
    offer: str | None
    offer_status: OfferStatus | None
    offer_status_label: str | None
    title: str
    description: str
    external_reference: str
    effort_type: str
    effort_rate: Decimal | None = Field(
        description="Requires the controlling feature, null otherwise."
    )
    service_hours: Decimal
    logged_hours: Decimal
    invoiced_hours: Decimal = Field(description="Logged hours on invoices.")
    not_invoiced_hours: Decimal = Field(description="Logged hours not invoiced yet.")
    cost: Decimal | None
    logged_cost: Decimal
    is_optional: bool
    is_logging_allowed: bool


class ServiceFilter(Schema):
    q: SearchQuery = ""
    project: ProjectID = None
    offer: int | None = Field(default=None, description="ID of the offer.")
    external_reference: str | None = Field(default=None, description="Exact match")


def _sum_of(model, field, **filters):
    """Subquery summing up ``field`` of the service's logbook entries"""
    return Subquery(
        model.objects
        .filter(service=OuterRef("pk"), **filters)
        .order_by()
        .values("service")
        .annotate(total=Sum(field))
        .values("total"),
        output_field=DecimalField(),
    )


def _services():
    return (
        Service.objects
        .select_related("project__customer", "offer__project")
        .annotate(
            logged_hours=_sum_of(LoggedHours, "hours"),
            invoiced_hours=_sum_of(LoggedHours, "hours", invoice_service__isnull=False),
            not_invoiced_hours=_sum_of(
                LoggedHours, "hours", invoice_service__isnull=True
            ),
            logged_cost=_sum_of(LoggedCost, "cost"),
        )
        .order_by("project", "offer_id", "position", "pk")
    )


def _service_out(service, request, *, controlling):
    return {
        "id": service.id,
        "url": request.build_absolute_uri(
            f"{service.project.get_absolute_url()}#service{service.pk}"
        ),
        "project": project_summary(service.project, request),
        "offer_id": service.offer_id,
        "offer": service.offer.code if service.offer else None,
        "offer_status": key("offer_status", service.offer.status)
        if service.offer
        else None,
        "offer_status_label": service.offer.get_status_display()
        if service.offer
        else None,
        "title": service.title,
        "description": service.description,
        "external_reference": service.external_reference,
        "effort_type": service.effort_type,
        "effort_rate": service.effort_rate if controlling else None,
        "service_hours": service.service_hours,
        "logged_hours": service.logged_hours or Z1,
        "invoiced_hours": service.invoiced_hours or Z1,
        "not_invoiced_hours": service.not_invoiced_hours or Z1,
        "cost": service.cost,
        "logged_cost": service.logged_cost or Z2,
        "is_optional": service.is_optional,
        "is_logging_allowed": service.is_logging_allowed(),
    }


class ServiceTypeOut(Schema):
    id: int
    title: str
    hourly_rate: Decimal


@router.get("/service-types/", response=list[ServiceTypeOut])
def service_type_list(request):
    """The service types; services and planned work take their titles, they
    suggest the effort type (their title) and the hourly rate of services"""
    return [
        {"id": st.id, "title": st.title, "hourly_rate": st.hourly_rate}
        for st in ServiceType.objects.all()
    ]


@router.get("/services/", response=list[ServiceOut])
@paginate
def service_list(request, filters: Query[ServiceFilter]):
    """Services with their logged hours and costs

    Same as on the project page: rates and amounts other than costs require
    the controlling feature (see the offers and the project statistics)."""
    services = _services()
    if filters.project:
        services = services.filter(project=filters.project)
    if filters.offer:
        services = services.filter(offer=filters.offer)
    if filters.external_reference:
        services = services.filter(external_reference=filters.external_reference)
    if filters.q:
        services = services.search(filters.q)
    controlling = request.user.features[FEATURES.CONTROLLING]
    return Serialized(
        services,
        lambda service: _service_out(service, request, controlling=controlling),
    )


class ServiceFields(InputSchema):
    """Fields which aren't given are left alone, ``null`` clears values"""

    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, description="Null removes it.")
    external_reference: str | None = Field(
        default=None,
        max_length=500,
        description="E.g. the URL of an issue, null removes it.",
    )
    service_type: str | None = Field(
        default=None,
        description="Title of a service type. Fills in the effort type and the"
        " hourly rate unless they are given too.",
    )
    effort_type: str | None = Field(default=None, max_length=50)
    hours: Number | None = Field(default=None, ge=0)
    hourly_rate: Number | None = Field(default=None, ge=0)
    cost: Number | None = Field(
        default=None, description="Fixed costs in addition to hours."
    )
    third_party_costs: Number | None = Field(
        default=None,
        ge=0,
        description="Total incl. tax for third parties contained in the cost.",
    )
    is_optional: bool | None = Field(default=None, description="Not part of the total.")


class ServicePatch(ServiceFields):
    """Fields which aren't given are left alone, ``null`` clears values

    Services of offers which have been sent or accepted can't be changed
    anymore, only their external reference can."""

    offer: int | None = Field(
        default=None,
        description="ID of an offer of the same project which is in preparation"
        " or a service group, null removes the service from its offer.",
    )


class ServiceCreate(ServiceFields):
    title: str = Field(min_length=1, max_length=200)
    project: int | None = Field(
        default=None, description="Defaults to the project of the offer."
    )
    offer: int | None = Field(
        default=None,
        description="ID of an offer of the project which is in preparation or a"
        " service group.",
    )
    after: int | None = Field(
        default=None,
        description="ID of the service of the same offer (or of the services"
        " without offer) after which the new one is inserted, defaults to the end.",
    )


# Names in the API and in the form
SERVICE_FORM_FIELDS = {
    "offer": "offer",
    "title": "title",
    "description": "description",
    "external_reference": "external_reference",
    "effort_type": "effort_type",
    "hours": "effort_hours",
    "hourly_rate": "effort_rate",
    "cost": "cost",
    "third_party_costs": "third_party_costs",
    "is_optional": "is_optional",
}


def _service_values(values, fields):
    """Apply the fields of the API to the data for the ``ServiceForm``"""
    if (title := fields.get("service_type")) is not None:
        service_type = ServiceType.objects.filter(title=title).first()
        if not service_type:
            raise ValidationError([
                {
                    "loc": ["body", "data", "service_type"],
                    "msg": _("Unknown service type %r.") % title,
                }
            ])
        if "effort_type" not in fields:
            values["effort_type"] = service_type.title
        if "hourly_rate" not in fields:
            values["effort_rate"] = service_type.hourly_rate
    for field, form_field in SERVICE_FORM_FIELDS.items():
        if field not in fields:
            continue
        value = fields[field]
        if field == "is_optional":
            values[form_field] = bool(value)
        elif isinstance(value, str):
            values[form_field] = value if field == "description" else value.strip()
        else:
            values[form_field] = "" if value is None else value
    return values


def _service_result(service, request, *, dry_run=False, created=False):
    result = _service_out(
        _services().get(pk=service.pk),
        request,
        controlling=request.user.features[FEATURES.CONTROLLING],
    )
    if dry_run and created:
        result |= {"id": None, "url": None}
    return result


@router.post("/services/", response=ServiceOut)
def service_create(
    request,
    data: ServiceCreate,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create a service, validated with the form of the web interface, at
    the end of its offer (or of the services without offer) or after another
    service

    Warnings of the web interface (e.g. ``unspecific-service``) are errors
    unless they are ignored. The ID and the URL are null with ``dry_run``."""
    fields = data.model_dump(exclude_unset=True)
    if data.project:
        project = get_object_or_404(Project, pk=data.project)
    elif data.offer:
        project = get_object_or_404(
            Offer.objects.select_related("project"), pk=data.offer
        ).project
    else:
        raise ValidationError([
            {
                "loc": ["body", "data", "project"],
                "msg": _("Either the project or the offer is required."),
            }
        ])
    values = form_data(ServiceForm(project=project, request=request))
    values = _service_values(values, fields)
    form = ServiceForm(values, project=project, request=request)
    validate_form(
        form,
        fields={v: [k] for k, v in SERVICE_FORM_FIELDS.items()},
        ignore_warnings=ignore_warnings,
    )

    group = list(
        Service.objects.filter(
            project=project, offer=form.cleaned_data.get("offer")
        ).order_by("position", "pk")
    )
    if data.after is not None and data.after not in {s.pk for s in group}:
        raise ValidationError([
            {
                "loc": ["body", "data", "after"],
                "msg": _(
                    "The offer (or the services without offer) has no service"
                    " with this ID."
                ),
            }
        ])

    with transaction.atomic():
        service = form.save()
        if data.after is not None:
            # Right after that service, also when a heading follows it
            items = offer_items(
                services=group,
                headings=service.offer.headings.all() if service.offer else [],
            )
            after = next(
                item
                for item in items
                if isinstance(item, Service) and item.pk == data.after
            )
            items.insert(1 + items.index(after), service)
            save_positions(items)
        result = _service_result(service, request, dry_run=dry_run, created=True)
        if dry_run:
            transaction.set_rollback(True)
    return result


@router.patch("/services/{int:service_id}/", response=ServiceOut)
def service_update(
    request,
    service_id: int,
    data: ServicePatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change a service or move it to another offer, validated with the form
    of the web interface

    Services of offers which have been sent or accepted can't be changed
    anymore, only their external reference can. Warnings of the web
    interface about the changed fields (e.g. ``unspecific-service``) are
    errors unless they are ignored."""
    service = get_object_or_404(Service.objects.select_related("offer"), pk=service_id)
    fields = data.model_dump(exclude_unset=True)
    if service.offer and service.offer.status > Offer.SERVICE_GROUP:
        if locked := [f for f in fields if f != "external_reference"]:
            raise ValidationError([
                {
                    "loc": ["body", "data", field],
                    "msg": _(
                        "The service is bound to an offer which is not in"
                        " preparation anymore."
                    ),
                }
                for field in locked
            ])
    values = form_data(ServiceForm(instance=service, request=request))
    values = _service_values(values, fields)
    form = ServiceForm(values, instance=service, request=request)
    validate_form(
        form,
        fields={v: [k] for k, v in SERVICE_FORM_FIELDS.items()},
        ignore_warnings=ignore_warnings,
    )

    with transaction.atomic():
        service = form.save()
        result = _service_result(service, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


@router.delete("/services/{int:service_id}/", response=ServiceOut)
def service_delete(request, service_id: int, *, dry_run: DryRun = False):
    """Delete a service like in the web interface: not when it is bound to an
    offer which has been sent (service groups are fine), and not when hours
    or costs have been logged on it

    Returns the deleted service."""
    service = get_object_or_404(Service.objects.select_related("offer"), pk=service_id)
    errors = []
    if service.offer and not service.offer.services_changeable:
        errors.append({
            "loc": ["path", "service_id"],
            "msg": _(
                "Cannot delete a service bound to an offer"
                " which is not in preparation anymore."
            ),
        })
    if service.loggedhours.exists() or service.loggedcosts.exists():
        errors.append({
            "loc": ["path", "service_id"],
            "msg": _(
                "Hours or costs have been logged on this service, it cannot be deleted."
            ),
        })
    if service.is_invoiced:
        errors.append({
            "loc": ["path", "service_id"],
            "msg": _("This service has been invoiced already, it cannot be deleted."),
        })
    if errors:
        raise ValidationError(errors)
    result = _service_result(service, request)
    with transaction.atomic():
        try:
            service.delete()
        except ProtectedError as exc:
            raise ValidationError([
                {
                    "loc": ["path", "service_id"],
                    "msg": _(
                        "Cannot delete '%(object)s'"
                        " because of related objects (%(related)s)."
                    )
                    % {
                        "object": service,
                        "related": ", ".join(
                            str(o) for o in islice(exc.protected_objects, 10)
                        ),
                    },
                }
            ]) from exc
        if dry_run:
            transaction.set_rollback(True)
    return result


class ServiceOrder(InputSchema):
    services: list[int] = Field(
        description="The IDs of all services of one offer, or of all services"
        " without offer of one project, in the new order."
    )


@router.post("/services/reorder/", response=list[ServiceOut])
def service_reorder(request, data: ServiceOrder, *, dry_run: DryRun = False):
    """Reorder the services of an offer, or the services without offer of a
    project, like in the web interface (where services are reordered by
    dragging them)"""
    services = {
        s.pk: s
        for s in Service.objects.filter(pk__in=data.services).select_related("offer")
    }
    first = services.get(data.services[0]) if data.services else None
    group = (
        set(
            Service.objects.filter(
                project=first.project_id, offer=first.offer_id
            ).values_list("pk", flat=True)
        )
        if first
        else set()
    )
    if not first or len(data.services) != len(group) or set(data.services) != group:
        raise ValidationError([
            {
                "loc": ["body", "data", "services"],
                "msg": _(
                    "Expected the IDs of all services of one offer, or of all"
                    " services without offer of one project, once."
                ),
            }
        ])
    if first.offer and not first.offer.services_changeable:
        raise ValidationError([
            {
                "loc": ["body", "data", "services"],
                "msg": _("Services of offers which have been sent can't be reordered."),
            }
        ])
    controlling = request.user.features[FEATURES.CONTROLLING]
    with transaction.atomic():
        # The offer's headings stay in their place
        reorder_services(
            [services[pk] for pk in data.services],
            headings=first.offer.headings.all() if first.offer else [],
        )
        ordered = {s.pk: s for s in _services().filter(pk__in=data.services)}
        result = [
            _service_out(ordered[pk], request, controlling=controlling)
            for pk in data.services
        ]
        if dry_run:
            transaction.set_rollback(True)
    return result


class ReassignLogbookIn(InputSchema):
    to: int = Field(
        description="ID of a service of the same project which allows logging"
    )
    include_invoiced: bool = Field(
        default=False,
        description="Also reassign invoiced entries; otherwise they stay with"
        " the service their invoice lines refer to.",
    )


class ReassignLogbookOut(Schema):
    hours: int = Field(description="Number of reassigned logged hours")
    costs: int = Field(description="Number of reassigned logged costs")
    from_: ServiceOut = Field(alias="from")
    to: ServiceOut


@router.post(
    "/services/{int:service_id}/reassign-logbook/",
    response=ReassignLogbookOut,
    by_alias=True,
)
def service_reassign_logbook(
    request, service_id: int, data: ReassignLogbookIn, *, dry_run: DryRun = False
):
    """Reassign the logged hours and costs of a service to another service,
    validated with the form of the web interface

    Merge services to also move the invoice lines and delete the service."""
    service = get_object_or_404(Service, pk=service_id)
    form = ReassignLogbookForm(
        {"service": data.to, "include_invoiced": data.include_invoiced or ""},
        instance=service,
        request=request,
    )
    if not form.is_valid(ignore_warnings=True):
        raise_form_errors(form, fields={"service": ["to"]})

    controlling = request.user.features[FEATURES.CONTROLLING]
    with transaction.atomic():
        hours, costs = form.logbook_entries()
        counts = {"hours": hours.count(), "costs": costs.count()}
        target = form.save()
        services = {s.pk: s for s in _services().filter(pk__in=[service.pk, target.pk])}
        result = counts | {
            "from": _service_out(
                services[service.pk], request, controlling=controlling
            ),
            "to": _service_out(services[target.pk], request, controlling=controlling),
        }
        if dry_run:
            transaction.set_rollback(True)
    return result


class ServiceMoveIn(InputSchema):
    project: int | str = Field(description="ID or code of an open project.")


@router.post("/services/{int:service_id}/move/", response=ServiceOut)
def service_move(
    request,
    service_id: int,
    data: ServiceMoveIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Move a service with its logged hours and costs to another open
    project, validated with the form of the web interface

    Invoiced services, services with invoiced hours or costs, services with
    logged hours or costs on closed projects and services bound to an offer
    stay where they are. A flat rate of the new project is
    applied to the service, a warning (``new-project-has-flat-rate``) when it
    changes the service's rate."""
    service = get_object_or_404(Service, pk=service_id)
    return patch_with_form(
        ServiceMoveForm.__wrapped__,  # Without the "modal" prefix
        service,
        data,
        request,
        out=lambda service: _service_result(service, request),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map={"project": object_pk(Project.objects.all())},
    )


class ServiceMergeIn(InputSchema):
    into: int = Field(description="ID of the service of the same project to keep")


@router.post("/services/{int:service_id}/merge/", response=ServiceOut)
def service_merge(
    request,
    service_id: int,
    data: ServiceMergeIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Merge a service into another service of the same project, like in
    the web interface: logged hours and costs (also invoiced ones), invoice
    lines, timestamps and pins move, the merged service is deleted

    Services of offers which have been sent can't be merged (service groups
    can).
    Different effort types or rates are a warning (``different-rate``), the
    logged hours are valued with the rate of the service kept."""
    service = get_object_or_404(Service, pk=service_id)
    form = ServiceMergeForm(
        {"into": data.into}, instance=service, request=request, prefix=""
    )
    validate_form(form, ignore_warnings=ignore_warnings)

    controlling = request.user.features[FEATURES.CONTROLLING]
    with transaction.atomic():
        keep = form.save()
        result = _service_out(
            _services().get(pk=keep.pk), request, controlling=controlling
        )
        if dry_run:
            transaction.set_rollback(True)
    return result
