import datetime as dt
from collections import defaultdict
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
    owned_by: str | None


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
    short_name: str
    planning_hours_per_day: Decimal


class MilestoneOut(Schema):
    id: int
    title: str
    date: dt.date
    phase_starts_on: dt.date | None
    estimated_total_hours: Decimal


class PlannedWorkOut(Schema):
    title: str
    user: str | None
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


class PlanningContext(Schema):
    project: ProjectOut
    offers: list[OfferOut]
    users: list[UserOut]
    service_types: list[str]
    milestones: list[MilestoneOut]
    planned_work: list[PlannedWorkOut]
    absences: list[AbsenceOut]
    import_schema: dict


def plannable_users():
    """Active users by short name, leaving out those without a unique short name

    The planning context is sent to LLMs, so it identifies people only by
    their short name, not by their email address or full name."""
    users = defaultdict(list)
    for user in User.objects.filter(is_active=True).exclude(_short_name=""):
        users[user._short_name].append(user)
    return {
        short_name: matches[0]
        for short_name, matches in sorted(users.items())
        if len(matches) == 1
    }


def project_planning_context(project):
    """Everything needed to plan the project, and the schema of the import"""
    offers = (
        project.offers
        .exclude(status=Offer.DECLINED)
        .select_related("project")
        .prefetch_related("services")
    )
    users = plannable_users()
    short_names = {user.pk: short_name for short_name, user in users.items()}
    service_types = list(ServiceType.objects.values_list("title", flat=True))
    today = dt.date.today()
    absences = (
        Absence.objects
        .filter(
            user__in=users.values(),
            starts_on__lte=today + dt.timedelta(days=366),
        )
        .exclude(reason=Absence.CORRECTION)
        .exclude(ends_on__lt=monday(today))
        .exclude(ends_on__isnull=True, starts_on__lt=monday(today))
        .order_by("starts_on")
    )

    return PlanningContext.model_validate({
        "project": {
            "id": project.id,
            "code": project.code,
            "title": project.title,
            "description": project.description,
            "customer": project.customer.name,
            "owned_by": short_names.get(project.owned_by_id),
        },
        "offers": [
            {
                "code": offer.code,
                "title": offer.title,
                "description": offer.description,
                "status": offer.get_status_display(),
                "services": list(offer.services.all()),
            }
            for offer in offers
        ],
        "users": [
            {
                "short_name": short_name,
                "planning_hours_per_day": user.planning_hours_per_day,
            }
            for short_name, user in users.items()
        ],
        "service_types": service_types,
        "milestones": list(project.milestones.all()),
        "planned_work": [
            {
                "title": pw.title,
                "user": short_names.get(pw.user_id),
                "service_type": pw.service_type.title if pw.service_type else None,
                "offer": pw.offer.code if pw.offer else None,
                "milestone": pw.milestone_id,
                "weeks": sorted(pw.weeks),
                "planned_hours": pw.planned_hours,
                "is_provisional": pw.is_provisional,
            }
            for pw in project.planned_work.select_related(
                "service_type", "offer__project"
            )
        ],
        "absences": [
            {
                "user": short_names[absence.user_id],
                "starts_on": absence.starts_on,
                "ends_on": absence.ends_on,
                "days": absence.days,
            }
            for absence in absences
        ],
        "import_schema": planning_import_schema(
            users=list(users),
            service_types=service_types,
            offers=[offer.code for offer in offers],
        ),
    })


@router.get("/projects/{project_id}/planning/context/", response=PlanningContext)
def planning_context(request, project_id: int):
    return project_planning_context(
        get_object_or_404(
            Project.objects.select_related("customer", "owned_by"), pk=project_id
        )
    )


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
    users = plannable_users()
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
