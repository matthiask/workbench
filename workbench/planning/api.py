import datetime as dt
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from ninja import Query, Router, Schema
from ninja.errors import ValidationError

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.offers.models import Offer
from workbench.planning.models import ExternalWork, Milestone, PlannedWork
from workbench.planning.reporting import Planning
from workbench.planning.schemas import (
    PlannedWorkIn,
    PlannedWorkPatch,
    PlanningImport,
    planning_import_schema,
)
from workbench.projects.api import ProjectSummary, project_summary
from workbench.projects.models import Project
from workbench.services.models import ServiceType
from workbench.tools.api import (
    DateRangeFilter,
    Hours,
    UsersFilter,
    date_range,
    filter_users,
    full_clean,
)
from workbench.tools.formats import Z1
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
    id: int
    title: str
    user: str | None
    service_type: str | None
    offer: str | None
    milestone: int | None
    weeks: list[dt.date]
    planned_hours: Decimal
    is_provisional: bool
    notes: str


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
    """Active users by short name

    The planning context is sent to LLMs, so it identifies people only by
    their short name, not by their email address or full name."""
    return {
        user._short_name: user
        for user in User.objects
        .filter(is_active=True)
        .exclude(_short_name="")
        .order_by("_short_name")
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
                "id": pw.id,
                "title": pw.title,
                "user": short_names.get(pw.user_id),
                "service_type": pw.service_type.title if pw.service_type else None,
                "offer": pw.offer.code if pw.offer else None,
                "milestone": pw.milestone_id,
                "weeks": sorted(pw.weeks),
                "planned_hours": pw.planned_hours,
                "is_provisional": pw.is_provisional,
                "notes": pw.notes,
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
    service_type: str | None
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
    deleted_milestones: list[int] = []
    deleted_planned_work: list[int] = []
    warnings: list[ImportWarning]


def _hours(value):
    return Decimal(str(value)).quantize(Decimal("0.1"))


def _lookups(project):
    """What planned work of the project may refer to"""
    return {
        "users": {
            short_name.casefold(): user
            for short_name, user in plannable_users().items()
        },
        "service_types": {st.title: st for st in ServiceType.objects.all()},
        "offers": {
            offer.code: offer
            for offer in project.offers.exclude(status=Offer.DECLINED).select_related(
                "project"
            )
        },
        "milestones": {m.pk: m for m in project.milestones.all()},
    }


def _apply_planned_work(  # noqa: C901
    pw, values, lookups, *, new_milestones, loc, errors, warnings
):
    """Set the given fields of planned work, shared by the import and the
    endpoints changing single planned work"""
    for field in ["title", "notes", "is_provisional"]:
        if field in values:
            setattr(pw, field, values[field])
    if "weeks" in values:
        pw.weeks = sorted({monday(week) for week in values["weeks"]})
    if "planned_hours" in values:
        pw.planned_hours = _hours(values["planned_hours"])

    if "user" in values:
        if user := lookups["users"].get(values["user"].casefold()):
            pw.user = user
        else:
            errors.append({
                "loc": [*loc, "user"],
                "msg": _("Unknown or inactive user %r.") % values["user"],
            })

    if "service_type" in values:
        if service_type := lookups["service_types"].get(values["service_type"]):
            pw.service_type = service_type
        else:
            errors.append({
                "loc": [*loc, "service_type"],
                "msg": _("Unknown service type %r.") % values["service_type"],
            })

    if "offer" in values:
        if values["offer"] is None:
            pw.offer = None
        elif offer := lookups["offers"].get(values["offer"]):
            pw.offer = offer
        else:
            errors.append({
                "loc": [*loc, "offer"],
                "msg": _("Unknown or declined offer %r.") % values["offer"],
            })

    if "milestone" in values:
        key = values["milestone"]
        if key is None:
            pw.milestone = None
        elif milestone := (
            new_milestones.get(key)
            if isinstance(key, str)
            else lookups["milestones"].get(key)
        ):
            pw.milestone = milestone
        else:
            errors.append({
                "loc": [*loc, "milestone"],
                "msg": _("Unknown milestone %r.") % key,
            })

    if pw.milestone and pw.weeks:
        if after := [w for w in pw.weeks if w >= monday(pw.milestone.date)]:
            warnings.append({
                "loc": [*loc, "weeks"],
                "msg": _(
                    "Work is planned in or after the week of the"
                    " milestone %(milestone)r: %(weeks)s"
                )
                % {
                    "milestone": pw.milestone.title,
                    "weeks": ", ".join(week.isoformat() for week in after),
                },
            })

    full_clean(
        pw,
        loc,
        errors,
        exclude=["user", "service_type", "offer", "milestone", "created_by"],
    )


def _import_result(*, milestones=(), planned_work=(), warnings=(), **deleted):
    return {
        "milestones": list(milestones),
        "planned_work": [
            {
                "id": pw.pk,
                "title": pw.title,
                "user": pw.user.get_short_name(),
                "service_type": pw.service_type.title if pw.service_type else None,
                "offer": pw.offer.code if pw.offer else None,
                "milestone": pw.milestone.title if pw.milestone else None,
                "weeks": pw.weeks,
                "planned_hours": pw.planned_hours,
                "is_provisional": pw.is_provisional,
            }
            for pw in planned_work
        ],
        "warnings": list(warnings),
        **deleted,
    }


def _existing(objects, ids, loc, errors, what):
    """The objects of the project with the given IDs"""
    found = []
    for index, pk in enumerate(ids):
        if pk in objects:
            found.append(objects[pk])
        else:
            errors.append({
                "loc": [*loc, index],
                "msg": _("%(what)s %(id)s doesn't belong to this project.")
                % {"what": capfirst(what), "id": pk},
            })
    return found


@router.post("/projects/{project_id}/planning/import/", response=ImportResult)
def planning_import(
    request, project_id: int, data: PlanningImport, *, dry_run: bool = False
):
    """Add, update and delete milestones and planned work of the project

    Entries with an ``id`` update existing ones (only the given fields),
    entries without add new ones. Nothing is deleted unless listed in
    ``delete_milestones`` or ``delete_planned_work``. Nothing is saved if
    anything is invalid or with ``dry_run``."""
    project = get_object_or_404(Project, pk=project_id)
    lookups = _lookups(project)
    existing_work = {pw.pk: pw for pw in project.planned_work.all()}
    errors = []
    warnings = []

    milestones = []
    new_milestones = {}
    for index, item in enumerate(data.milestones):
        loc = ["body", "data", "milestones", index]
        if item.id is not None:
            if not (milestone := lookups["milestones"].get(item.id)):
                errors.append({
                    "loc": [*loc, "id"],
                    "msg": _("Unknown milestone %r.") % item.id,
                })
                continue
        else:
            milestone = Milestone(project=project)
        if item.key is not None:
            if item.key in new_milestones:
                errors.append({
                    "loc": [*loc, "key"],
                    "msg": _("Duplicate milestone key %r.") % item.key,
                })
            new_milestones[item.key] = milestone
        milestone.title = item.title
        milestone.date = item.date
        milestone.phase_starts_on = item.phase_starts_on
        milestone.estimated_total_hours = _hours(item.estimated_total_hours)
        full_clean(milestone, loc, errors)
        milestones.append(milestone)

    planned_work = []
    for index, item in enumerate(data.planned_work):
        loc = ["body", "data", "planned_work", index]
        if item.id is not None:
            if not (pw := existing_work.get(item.id)):
                errors.append({
                    "loc": [*loc, "id"],
                    "msg": _("Unknown planned work %r.") % item.id,
                })
                continue
            values = item.model_dump(exclude={"id"}, exclude_unset=True)
        else:
            pw = PlannedWork(project=project, created_by=request.user)
            values = item.model_dump(exclude={"id"})
        _apply_planned_work(
            pw,
            values,
            lookups,
            new_milestones=new_milestones,
            loc=loc,
            errors=errors,
            warnings=warnings,
        )
        planned_work.append(pw)

    delete_milestones = _existing(
        lookups["milestones"],
        data.delete_milestones,
        ["body", "data", "delete_milestones"],
        errors,
        _("milestone"),
    )
    delete_work = _existing(
        existing_work,
        data.delete_planned_work,
        ["body", "data", "delete_planned_work"],
        errors,
        _("planned work"),
    )

    if errors:
        raise ValidationError(errors)

    if not dry_run:
        with transaction.atomic():
            for milestone in milestones:
                milestone.save()
            for pw in planned_work:
                pw.save()
            for pw in delete_work:
                pw.delete()
            for milestone in delete_milestones:
                milestone.delete()

    return _import_result(
        milestones=milestones,
        planned_work=planned_work,
        warnings=warnings,
        deleted_milestones=data.delete_milestones,
        deleted_planned_work=data.delete_planned_work,
    )


@router.post("/projects/{project_id}/planning/work/", response=ImportResult)
def planned_work_create(
    request, project_id: int, data: PlannedWorkIn, *, dry_run: bool = False
):
    """Add planned work to the project"""
    if data.id is not None:
        raise ValidationError([
            {"loc": ["body", "data", "id"], "msg": _("Use PATCH to update work.")}
        ])
    project = get_object_or_404(Project, pk=project_id)
    return planning_import(
        request,
        project.pk,
        PlanningImport(planned_work=[data]),
        dry_run=dry_run,
    )


def _planned_work(work_id):
    return get_object_or_404(PlannedWork.objects.select_related("project"), pk=work_id)


@router.patch("/planning/work/{int:work_id}/", response=ImportResult)
def planned_work_update(
    request, work_id: int, data: PlannedWorkPatch, *, dry_run: bool = False
):
    """Change single fields of planned work"""
    pw = _planned_work(work_id)
    values = data.model_dump(exclude_unset=True)
    errors = []
    warnings = []
    _apply_planned_work(
        pw,
        values,
        _lookups(pw.project),
        new_milestones={},
        loc=["body", "data"],
        errors=errors,
        warnings=warnings,
    )
    if errors:
        raise ValidationError(errors)
    if not dry_run:
        pw.save()
    return _import_result(planned_work=[pw], warnings=warnings)


@router.delete("/planning/work/{int:work_id}/", response=ImportResult)
def planned_work_delete(request, work_id: int, *, dry_run: bool = False):
    """Delete planned work"""
    pw = _planned_work(work_id)
    if not dry_run:
        pw.delete()
    return _import_result(deleted_planned_work=[work_id])


class PlanningExportFilter(DateRangeFilter, UsersFilter):
    project: int | None = None
    campaign: int | None = None


def _mondays(date_from, date_until):
    week = monday(date_from)
    while week <= date_until:
        yield week
        week += dt.timedelta(days=7)


class ExportedOffer(Schema):
    id: int
    code: str
    title: str


class ExportedPlannedWork(Schema):
    id: int
    url: str
    project: ProjectSummary
    offer: ExportedOffer | None
    milestone: str | None
    user: str
    title: str
    service_type: str | None
    is_provisional: bool
    planned_hours: Hours
    hours_per_week: Hours
    hours_in_period: Hours
    weeks: list[dt.date]


class ExportedMilestone(Schema):
    id: int
    url: str
    project: ProjectSummary
    title: str
    date: dt.date
    phase_starts_on: dt.date | None
    estimated_total_hours: Hours


class ExportedExternalWork(Schema):
    id: int
    url: str
    project: ProjectSummary
    title: str
    provided_by: str
    service_type: str | None
    milestone: str | None
    weeks: list[dt.date]


class ExportedWeek(Schema):
    week: dt.date
    planned: Hours
    provisional: Hours


class Capacity(Schema):
    user: str
    weeks: dict[str, Hours]


class PlanningExport(Schema):
    since: dt.date | None
    until: dt.date | None
    weeks: list[ExportedWeek]
    planned_work: list[ExportedPlannedWork]
    milestones: list[ExportedMilestone]
    external_work: list[ExportedExternalWork]
    capacity: list[Capacity] | None


@router.get("/planning/export/", response=PlanningExport)
def planning_export(request, filters: Query[PlanningExportFilter]):
    """Planned work, milestones and external work, optionally of a project, a
    campaign, users or a team

    The period is the whole planning of projects and campaigns, otherwise
    the current and the next eleven weeks by default. Planned hours are
    distributed evenly over the weeks of the planned work. Milestones and
    external work are those of the projects with planned work, or of the
    project or campaign. The capacity (hours not planned yet, less absences
    and holidays) is reported for users and teams."""
    work = PlannedWork.objects.select_related(
        "project", "offer__project", "user", "service_type", "milestone"
    )
    milestones = Milestone.objects.select_related("project")
    external_work = ExternalWork.objects.select_related(
        "project", "provided_by", "service_type", "milestone"
    )
    if filters.project is not None:
        work = work.filter(project=filters.project)
    if filters.campaign is not None:
        work = work.filter(project__campaign=filters.campaign)
    users = filter_users(filters)
    if users is not None:
        work = work.filter(user__in=users)

    if (
        filters.period
        or filters.since
        or filters.until
        or (filters.project is None and filters.campaign is None)
    ):
        period = date_range(
            filters, default=[monday(), monday() + dt.timedelta(days=83)]
        )
        weeks = list(_mondays(*period))
        work = work.filter(weeks__overlap=weeks)
    else:
        weeks = sorted({week for pw in work for week in pw.weeks})
        period = [weeks[0], weeks[-1] + dt.timedelta(days=6)] if weeks else [None, None]
        weeks = list(_mondays(*period)) if weeks else []
    work = list(work)

    projects = Q(project__in={pw.project_id for pw in work})
    if filters.project is not None:
        projects |= Q(project=filters.project)
    if filters.campaign is not None:
        projects |= Q(project__campaign=filters.campaign)
    if weeks:
        milestones = milestones.filter(
            projects, date__range=[weeks[0], weeks[-1] + dt.timedelta(days=6)]
        )
        external_work = external_work.filter(projects, weeks__overlap=weeks)
    else:
        milestones = milestones.filter(projects)
        external_work = external_work.filter(projects)

    by_week = {week: {"planned": Z1, "provisional": Z1} for week in weeks}
    planned_work = []
    for pw in sorted(work, key=lambda pw: (min(pw.weeks), pw.project_id, pw.pk)):
        per_week = pw.planned_hours / len(pw.weeks)
        in_period = [week for week in pw.weeks if week in by_week]
        for week in in_period:
            by_week[week]["planned"] += per_week
            if pw.is_provisional:
                by_week[week]["provisional"] += per_week
        planned_work.append({
            "id": pw.id,
            "url": request.build_absolute_uri(pw.get_absolute_url()),
            "project": project_summary(pw.project, request),
            "offer": {"id": pw.offer.id, "code": pw.offer.code, "title": pw.offer.title}
            if pw.offer
            else None,
            "milestone": pw.milestone.title if pw.milestone else None,
            "user": pw.user.get_short_name(),
            "title": pw.title,
            "service_type": pw.service_type.title if pw.service_type else None,
            "is_provisional": pw.is_provisional,
            "planned_hours": pw.planned_hours,
            "hours_per_week": per_week,
            "hours_in_period": per_week * len(in_period),
            "weeks": sorted(pw.weeks),
        })

    capacity = None
    if users is not None and weeks:
        active = sorted(users.filter(is_active=True))
        if active:
            rows = Planning(weeks=weeks, users=active).capacity()["by_user"]
            capacity = [
                {
                    "user": user.get_short_name(),
                    "weeks": {
                        week.isoformat(): hours
                        for week, hours in zip(weeks, row["capacity"], strict=True)
                    },
                }
                for user, row in zip(active, rows, strict=True)
            ]

    return {
        "since": period[0],
        "until": period[1],
        "weeks": [{"week": week} | hours for week, hours in by_week.items()],
        "planned_work": planned_work,
        "milestones": [
            {
                "id": milestone.id,
                "url": request.build_absolute_uri(milestone.urls["detail"]),
                "project": project_summary(milestone.project, request),
                "title": milestone.title,
                "date": milestone.date,
                "phase_starts_on": milestone.phase_starts_on,
                "estimated_total_hours": milestone.estimated_total_hours,
            }
            for milestone in milestones.order_by("date", "pk")
        ],
        "external_work": [
            {
                "id": ew.id,
                "url": request.build_absolute_uri(ew.get_absolute_url()),
                "project": project_summary(ew.project, request),
                "title": ew.title,
                "provided_by": ew.provided_by.name,
                "service_type": ew.service_type.title if ew.service_type else None,
                "milestone": ew.milestone.title if ew.milestone else None,
                "weeks": sorted(ew.weeks),
            }
            for ew in sorted(external_work, key=lambda ew: (min(ew.weeks), ew.pk))
        ],
        "capacity": capacity,
    }
