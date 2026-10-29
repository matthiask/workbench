import datetime as dt
from decimal import Decimal

from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.offers.models import Offer
from workbench.planning.schemas import planning_import_schema
from workbench.projects.models import Project
from workbench.services.models import ServiceType
from workbench.tools.validation import monday


router = Router(tags=["planning"])


class ProjectOut(Schema):
    id: int
    code: str
    title: str
    description: str
    customer: str
    owned_by: str


class ServiceOut(Schema):
    title: str
    description: str
    effort_type: str
    service_hours: Decimal
    is_optional: bool


class OfferOut(Schema):
    code: str
    title: str
    description: str
    status: str
    services: list[ServiceOut]


class UserOut(Schema):
    email: str
    name: str
    planning_hours_per_day: Decimal


class MilestoneOut(Schema):
    id: int
    title: str
    date: dt.date
    phase_starts_on: dt.date | None
    estimated_total_hours: Decimal


class PlannedWorkOut(Schema):
    title: str
    user: str
    service_type: str | None
    offer: str | None
    milestone: int | None
    weeks: list[dt.date]
    planned_hours: Decimal
    is_provisional: bool


class AbsenceOut(Schema):
    user: str
    starts_on: dt.date
    ends_on: dt.date | None
    days: Decimal
    reason: str


class PlanningContext(Schema):
    project: ProjectOut
    offers: list[OfferOut]
    users: list[UserOut]
    service_types: list[str]
    milestones: list[MilestoneOut]
    planned_work: list[PlannedWorkOut]
    absences: list[AbsenceOut]
    import_schema: dict


@router.get("/projects/{project_id}/planning/context/", response=PlanningContext)
def planning_context(request, project_id: int):
    """Everything needed to plan the project, and the schema of the import"""
    project = get_object_or_404(
        Project.objects.select_related("customer", "owned_by"), pk=project_id
    )
    offers = (
        project.offers
        .exclude(status=Offer.DECLINED)
        .select_related("project")
        .prefetch_related("services")
    )
    users = User.objects.filter(is_active=True).order_by("_full_name", "email")
    service_types = list(ServiceType.objects.values_list("title", flat=True))
    today = dt.date.today()
    absences = (
        Absence.objects
        .filter(
            user__is_active=True,
            starts_on__lte=today + dt.timedelta(days=366),
        )
        .exclude(ends_on__lt=monday(today))
        .exclude(ends_on__isnull=True, starts_on__lt=monday(today))
        .select_related("user")
        .order_by("starts_on")
    )

    return {
        "project": {
            "id": project.id,
            "code": project.code,
            "title": project.title,
            "description": project.description,
            "customer": project.customer.name,
            "owned_by": project.owned_by.email,
        },
        "offers": [
            {
                "code": offer.code,
                "title": offer.title,
                "description": offer.description,
                "status": offer.get_status_display(),
                "services": offer.services.all(),
            }
            for offer in offers
        ],
        "users": [
            {
                "email": user.email,
                "name": user.get_full_name(),
                "planning_hours_per_day": user.planning_hours_per_day,
            }
            for user in users
        ],
        "service_types": service_types,
        "milestones": project.milestones.all(),
        "planned_work": [
            {
                "title": pw.title,
                "user": pw.user.email,
                "service_type": pw.service_type.title if pw.service_type else None,
                "offer": pw.offer.code if pw.offer else None,
                "milestone": pw.milestone_id,
                "weeks": sorted(pw.weeks),
                "planned_hours": pw.planned_hours,
                "is_provisional": pw.is_provisional,
            }
            for pw in project.planned_work.select_related(
                "user", "service_type", "offer__project"
            )
        ],
        "absences": [
            {
                "user": absence.user.email,
                "starts_on": absence.starts_on,
                "ends_on": absence.ends_on,
                "days": absence.days,
                "reason": absence.get_reason_display(),
            }
            for absence in absences
        ],
        "import_schema": planning_import_schema(
            users=[user.email for user in users],
            service_types=service_types,
            offers=[offer.code for offer in offers],
        ),
    }
