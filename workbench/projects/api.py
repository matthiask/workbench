import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Literal

from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError, ValidationError

from workbench.accounts.models import User
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedHours
from workbench.planning.models import PlannedWork
from workbench.projects.forms import ProjectForm
from workbench.projects.models import Project
from workbench.reporting.project_budget_statistics import project_budget_statistics
from workbench.reporting.squeeze import project_gross_margin
from workbench.tools.formats import Z1, Z2


router = Router(tags=["projects"])


class ProjectOut(Schema):
    id: int
    code: str
    url: str
    title: str
    description: str
    customer: str
    owned_by: str
    flat_rate: Decimal | None
    closed_on: dt.date | None


def project_out(project, request):
    return {
        "id": project.id,
        "code": project.code,
        "url": request.build_absolute_uri(project.get_absolute_url()),
        "title": project.title,
        "description": project.description,
        "customer": project.customer.name,
        "owned_by": project.owned_by.get_short_name(),
        "flat_rate": project.flat_rate,
        "closed_on": project.closed_on,
    }


@router.get("/projects/", response=list[ProjectOut])
def project_list(request, q: str = "", *, include_closed: bool = False):
    """Search projects, open projects only by default"""
    projects = Project.objects.select_related("customer", "owned_by")
    if not include_closed:
        projects = projects.open()
    if q:
        projects = projects.search(q)
    return [project_out(project, request) for project in projects[:50]]


@router.get("/projects/{int:project_id}/", response=ProjectOut)
def project_detail(request, project_id: int):
    return project_out(
        get_object_or_404(
            Project.objects.select_related("customer", "owned_by"), pk=project_id
        ),
        request,
    )


class ProjectIn(Schema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    customer: int = Field(description="ID of the customer organization.")
    contact: int | None = Field(
        default=None, description="ID of the contact person at the customer."
    )
    type: Literal["order", "maintenance", "internal"] = "order"
    owned_by: str | None = Field(
        default=None,
        description="Short name of the person responsible, defaults to the"
        " authenticated user.",
    )


class ProjectCreated(ProjectOut):
    id: int | None
    url: str | None


@router.post("/projects/", response=ProjectCreated)
def project_create(request, data: ProjectIn, *, dry_run: bool = False):
    """Create a project, validated like in the web interface

    Warnings of the web interface are errors here; nothing is saved if anything
    is invalid or with ``dry_run``."""
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
            "customer": data.customer,
            "contact": data.contact or "",
            "type": data.type,
            "owned_by": owned_by.pk,
        },
        request=request,
    )
    if not form.is_valid():
        raise ValidationError(
            [
                {
                    "loc": ["body", "data"] + ([field] if field != "__all__" else []),
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
        project = form.save()
        result = project_out(project, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
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
    offer_status: str | None
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
    status: str
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


@router.get("/projects/stats/", response=list[ProjectStats])
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
        Project.objects.filter(q).select_related("customer", "owned_by").order_by("pk")
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
                    "offer_status": service.offer.get_status_display()
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
                    "status": invoice.get_status_display(),
                    "invoiced_on": invoice.invoiced_on,
                    "total_excl_tax": invoice.total_excl_tax,
                    "third_party_costs": invoice.third_party_costs,
                }
                for invoice in invoices[project.id]
            ],
        }

    return [project_stats(project) for project in projects]
