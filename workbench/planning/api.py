import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Router, Schema
from ninja.errors import ValidationError

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.offers.models import Offer
from workbench.planning.models import Milestone, PlannedWork
from workbench.planning.schemas import PlanningImport, planning_import_schema
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


class ImportedMilestone(Schema):
    id: int | None
    title: str
    date: dt.date
    phase_starts_on: dt.date | None
    estimated_total_hours: Decimal


class ImportedPlannedWork(Schema):
    id: int | None
    title: str
    user: str
    service_type: str
    offer: str | None
    milestone: str | None
    weeks: list[dt.date]
    planned_hours: Decimal
    is_provisional: bool


class ImportWarning(Schema):
    loc: list[str | int]
    msg: str


class ImportResult(Schema):
    milestones: list[ImportedMilestone]
    planned_work: list[ImportedPlannedWork]
    warnings: list[ImportWarning]


def _hours(value):
    return Decimal(str(value)).quantize(Decimal("0.1"))


def _full_clean(instance, loc, errors, *, exclude=()):
    try:
        instance.full_clean(exclude=exclude)
    except DjangoValidationError as exc:
        errors.extend(
            {"loc": [*loc, field], "msg": message}
            for field, messages in exc.message_dict.items()
            for message in messages
        )


@router.post("/projects/{project_id}/planning/import/", response=ImportResult)
def planning_import(
    request, project_id: int, data: PlanningImport, *, dry_run: bool = False
):
    """Add milestones and planned work to the project

    Nothing is saved if anything is invalid or with ``dry_run``."""
    project = get_object_or_404(Project, pk=project_id)
    users = {user.email: user for user in User.objects.filter(is_active=True)}
    service_types = {st.title: st for st in ServiceType.objects.all()}
    offers = {
        offer.code: offer
        for offer in project.offers.exclude(status=Offer.DECLINED).select_related(
            "project"
        )
    }
    existing_milestones = {m.pk: m for m in project.milestones.all()}
    errors = []
    warnings = []

    milestones = {}
    for index, item in enumerate(data.milestones):
        loc = ["body", "data", "milestones", index]
        if item.key in milestones:
            errors.append({
                "loc": [*loc, "key"],
                "msg": _("Duplicate milestone key %r.") % item.key,
            })
        milestone = Milestone(
            project=project,
            title=item.title,
            date=item.date,
            phase_starts_on=item.phase_starts_on,
            estimated_total_hours=_hours(item.estimated_total_hours),
        )
        _full_clean(milestone, loc, errors)
        milestones[item.key] = milestone

    planned_work = []
    for index, item in enumerate(data.planned_work):
        loc = ["body", "data", "planned_work", index]
        pw = PlannedWork(
            project=project,
            created_by=request.user,
            title=item.title,
            notes=item.notes,
            weeks=sorted({monday(week) for week in item.weeks}),
            planned_hours=_hours(item.planned_hours),
            is_provisional=item.is_provisional,
        )

        if user := users.get(item.user):
            pw.user = user
        else:
            errors.append({
                "loc": [*loc, "user"],
                "msg": _("Unknown or inactive user %r.") % item.user,
            })

        if service_type := service_types.get(item.service_type):
            pw.service_type = service_type
        else:
            errors.append({
                "loc": [*loc, "service_type"],
                "msg": _("Unknown service type %r.") % item.service_type,
            })

        if item.offer is not None:
            if offer := offers.get(item.offer):
                pw.offer = offer
            else:
                errors.append({
                    "loc": [*loc, "offer"],
                    "msg": _("Unknown or declined offer %r.") % item.offer,
                })

        if item.milestone is not None:
            if milestone := (
                milestones.get(item.milestone)
                if isinstance(item.milestone, str)
                else existing_milestones.get(item.milestone)
            ):
                pw.milestone = milestone
                if after := [w for w in pw.weeks if w >= monday(milestone.date)]:
                    warnings.append({
                        "loc": [*loc, "weeks"],
                        "msg": _(
                            "Work is planned in or after the week of the"
                            " milestone %(milestone)r: %(weeks)s"
                        )
                        % {
                            "milestone": milestone.title,
                            "weeks": ", ".join(week.isoformat() for week in after),
                        },
                    })
            else:
                errors.append({
                    "loc": [*loc, "milestone"],
                    "msg": _("Unknown milestone %r.") % item.milestone,
                })

        _full_clean(
            pw,
            loc,
            errors,
            exclude=["user", "service_type", "offer", "milestone", "created_by"],
        )
        planned_work.append(pw)

    if errors:
        raise ValidationError(errors)

    if not dry_run:
        with transaction.atomic():
            for milestone in milestones.values():
                milestone.save()
            for pw in planned_work:
                pw.save()

    return {
        "milestones": list(milestones.values()),
        "planned_work": [
            {
                "id": pw.pk,
                "title": pw.title,
                "user": pw.user.get_full_name(),
                "service_type": pw.service_type.title,
                "offer": pw.offer.code if pw.offer else None,
                "milestone": pw.milestone.title if pw.milestone else None,
                "weeks": pw.weeks,
                "planned_hours": pw.planned_hours,
                "is_provisional": pw.is_provisional,
            }
            for pw in planned_work
        ],
        "warnings": warnings,
    }
