import datetime as dt
from collections import defaultdict
from decimal import Decimal
from itertools import islice
from typing import Literal

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
from workbench.api_keys import InvoiceStatus, OfferStatus, key
from workbench.contacts.api import (
    OrganizationOut,
    PersonSummary,
    organization_out,
    person_summary,
)
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.planning.models import PlannedWork
from workbench.projects.forms import ProjectForm, ReassignLogbookForm, ServiceForm
from workbench.projects.models import InternalType, Project, Service
from workbench.reporting.project_budget_statistics import project_budget_statistics
from workbench.reporting.squeeze import project_gross_margin
from workbench.services.models import ServiceType
from workbench.tools.api import (
    IGNORE_WARNINGS,
    Number,
    Serialized,
    form_data,
    raise_form_errors,
    validate_form,
)
from workbench.tools.formats import Z1, Z2


router = Router(tags=["projects"])


class ProjectSummary(Schema):
    id: int
    code: str
    title: str
    url: str


def project_summary(project, request):
    return {
        "id": project.id,
        "code": project.code,
        "title": project.title,
        "url": request.build_absolute_uri(project.get_absolute_url()),
    }


class ProjectOut(Schema):
    id: int
    code: str
    url: str
    title: str
    description: str
    customer: OrganizationOut
    contact: PersonSummary | None
    owned_by: str
    flat_rate: Decimal | None
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
        "internal_type": project.internal_type.name if project.internal_type else None,
        "flat_rate": project.flat_rate,
        "created_at": project.created_at,
        "closed_on": project.closed_on,
    }


class ProjectFilter(Schema):
    q: str = ""
    customer: int | None = None
    owned_by: str | None = None
    include_closed: bool = False


class InternalTypeOut(Schema):
    name: str
    description: str
    percentage: Decimal
    is_outreach: bool


@router.get("/projects/internal-types/", response=list[InternalTypeOut])
@paginate
def internal_type_list(request):
    """The internal types of internal projects, by their name in
    ``internal_type``"""
    return Serialized(
        InternalType.objects.order_by("ordering", "pk"),
        lambda internal_type: {
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
        "customer", "contact", "owned_by", "internal_type"
    ).order_by("-pk")
    if not filters.include_closed:
        projects = projects.open()
    if filters.customer:
        projects = projects.filter(customer=filters.customer)
    if filters.owned_by:
        projects = projects.filter(owned_by___short_name__iexact=filters.owned_by)
    if q := filters.q:
        projects = projects.search(q)
    return Serialized(projects, lambda project: project_out(project, request))


@router.get("/projects/{int:project_id}/", response=ProjectOut)
def project_detail(request, project_id: int):
    return project_out(
        get_object_or_404(
            Project.objects.select_related(
                "customer", "contact", "owned_by", "internal_type"
            ),
            pk=project_id,
        ),
        request,
    )


class ProjectIn(Schema):
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
        description="Name of the internal type, required for internal projects"
        " if the installation uses internal types.",
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
    dry_run: bool = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create a project, validated like in the web interface

    Warnings of the web interface are errors here unless ignored by their
    code; nothing is saved if anything is invalid or with ``dry_run``."""
    owned_by = request.user
    if data.owned_by is not None:
        owned_by = User.objects.filter(
            is_active=True, _short_name__iexact=data.owned_by
        ).first()
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


class ProjectPatch(Schema):
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
        description="Name of the internal type. Projects which aren't internal"
        " anymore lose it.",
    )
    owned_by: str | None = Field(default=None, description="Short name.")
    closed_on: dt.date | None = Field(
        default=None, description="Closes the project, null reopens it."
    )
    delete_planned_work: bool | None = Field(
        default=None,
        description="Required when closing a project whose offers in"
        " preparation (which are discarded) have planned work: delete it or"
        " keep it.",
    )


@router.patch("/projects/{int:project_id}/", response=ProjectOut)
def project_update(
    request,
    project_id: int,
    data: ProjectPatch,
    *,
    dry_run: bool = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change or close a project, validated like in the web interface

    Warnings of the web interface are errors here unless ignored by their
    code; nothing is saved if anything is invalid or with ``dry_run``."""
    project = get_object_or_404(Project, pk=project_id)
    values = form_data(ProjectForm(instance=project, request=request))
    patch = data.model_dump(exclude_unset=True)
    for field in ["title", "description", "customer", "contact", "type", "closed_on"]:
        if field in patch:
            values[field] = "" if patch[field] is None else patch[field]
    if patch.get("owned_by"):
        owned_by = User.objects.filter(
            is_active=True, _short_name__iexact=patch["owned_by"]
        ).first()
        if not owned_by:
            raise ValidationError([
                {
                    "loc": ["body", "data", "owned_by"],
                    "msg": _("Unknown or inactive user %r.") % patch["owned_by"],
                }
            ])
        values["owned_by"] = owned_by.pk
    if "internal_type" in patch:
        values["internal_type"] = _internal_type(patch["internal_type"])
    elif patch.get("type") and patch["type"] != Project.INTERNAL:
        values["internal_type"] = ""
    if data.delete_planned_work is not None:
        values["delete_planned_work"] = int(data.delete_planned_work)

    form = ProjectForm(values, instance=project, request=request)
    validate_form(form, ignore_warnings=ignore_warnings)

    with transaction.atomic():
        project = form.save()
        result = project_out(project, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


class StatsFilter(Schema):
    ids: list[int] = []
    open: bool = False
    closed_since: dt.date | None = None


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
    code: str
    title: str
    type: str
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
        .select_related("customer", "contact", "owned_by", "internal_type")
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
                    "code": invoice.code,
                    "title": invoice.title,
                    "type": invoice.get_type_display(),
                    "status": key("invoice_status", invoice.status),
                    "invoiced_on": invoice.invoiced_on,
                    "total_excl_tax": invoice.total_excl_tax,
                    "third_party_costs": invoice.third_party_costs,
                }
                for invoice in invoices[project.id]
            ],
        }

    return [project_stats(project) for project in projects]


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
    q: str = ""
    project: int | None = None
    offer: int | None = None
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
        .select_related("project", "offer__project")
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


class ServiceFields(Schema):
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
    dry_run: bool = False,
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
            index = 1 + [s.pk for s in group].index(data.after)
            group.insert(index, service)
            for position, s in enumerate(group, 1):
                Service.objects.filter(pk=s.pk).update(position=10 * position)
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
    dry_run: bool = False,
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
def service_delete(request, service_id: int, *, dry_run: bool = False):
    """Delete a service like in the web interface: not when it is bound to an
    offer which isn't in preparation anymore, and not when hours or costs
    have been logged on it

    Returns the deleted service."""
    service = get_object_or_404(Service.objects.select_related("offer"), pk=service_id)
    errors = []
    if service.offer and service.offer.status > Offer.IN_PREPARATION:
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


class ServiceOrder(Schema):
    services: list[int] = Field(
        description="The IDs of all services of one offer, or of all services"
        " without offer of one project, in the new order."
    )


@router.post("/services/reorder/", response=list[ServiceOut])
def service_reorder(request, data: ServiceOrder, *, dry_run: bool = False):
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
        for position, pk in enumerate(data.services, 1):
            Service.objects.filter(pk=pk).update(position=10 * position)
        ordered = {s.pk: s for s in _services().filter(pk__in=data.services)}
        result = [
            _service_out(ordered[pk], request, controlling=controlling)
            for pk in data.services
        ]
        if dry_run:
            transaction.set_rollback(True)
    return result


class ReassignLogbookIn(Schema):
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
    request, service_id: int, data: ReassignLogbookIn, *, dry_run: bool = False
):
    """Reassign the logged hours and costs of a service to another service,
    validated with the form of the web interface

    Services can't be deleted afterwards like in the web interface."""
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
