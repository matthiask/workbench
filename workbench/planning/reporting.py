import datetime as dt
from collections import defaultdict
from itertools import islice

from django.db import connections
from django.db.models import Sum
from django.utils.translation import gettext as _

from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedHours
from workbench.planning.models import PlannedWork, PlanningRequest
from workbench.tools.formats import Z1, Z2, local_date_format
from workbench.tools.validation import monday


def user_planning(user):
    weeks = list(islice(recurring(monday(), "weekly"), 52))

    by_week = defaultdict(lambda: Z1)
    by_project_and_week = defaultdict(lambda: defaultdict(lambda: Z1))
    projects_offers = defaultdict(lambda: defaultdict(list))
    project_ids = set()

    for pw in PlannedWork.objects.filter(
        user=user, weeks__overlap=weeks
    ).select_related("project__owned_by", "offer__project", "offer__owned_by"):
        per_week = (pw.planned_hours / len(pw.weeks)).quantize(Z2)
        for week in pw.weeks:
            by_week[week] += per_week
            by_project_and_week[pw.project][week] += per_week

        date_from = min(pw.weeks)
        date_until = max(pw.weeks) + dt.timedelta(days=6)

        projects_offers[pw.project][pw.offer].append(
            {
                "work": {
                    "id": pw.id,
                    "title": pw.title,
                    "planned_hours": pw.planned_hours,
                    "url": pw.get_absolute_url(),
                    "date_from": date_from,
                    "date_until": date_until,
                    "range": "{} – {}".format(
                        local_date_format(date_from, fmt="d.m."),
                        local_date_format(date_until, fmt="d.m."),
                    ),
                },
                "hours_per_week": [
                    per_week if week in pw.weeks else Z1 for week in weeks
                ],
            }
        )

        project_ids.add(pw.project.pk)

    for pr in PlanningRequest.objects.filter(receivers=user).select_related(
        "project__owned_by", "offer__project", "offer__owned_by"
    ):
        date_from = pr.earliest_start_on
        date_until = pr.completion_requested_on - dt.timedelta(days=1)

        requested_weeks = (pr.completion_requested_on - date_from).days // 7
        per_week = (pr.requested_hours / requested_weeks).quantize(Z2)

        projects_offers[pr.project][pr.offer].append(
            {
                "work": {  # FIXME
                    "id": pr.id,
                    "title": "{}: {}".format(_("Request"), pr.title),
                    "requested_hours": pr.requested_hours,
                    "planned_hours": pr.planned_hours,
                    "missing_hours": pr.requested_hours - pr.planned_hours,
                    "url": pr.get_absolute_url(),
                    "date_from": date_from,
                    "date_until": date_until,
                    "range": "{} – {}".format(
                        local_date_format(date_from, fmt="d.m."),
                        local_date_format(date_until, fmt="d.m."),
                    ),
                },
                "hours_per_week": [
                    per_week if date_from < week < date_until else Z1 for week in weeks
                ],
            }
        )

        project_ids.add(pr.project.pk)

    worked_hours_by_offer = defaultdict(lambda: Z1)
    worked_hours_by_project = defaultdict(lambda: Z1)
    for row in (
        LoggedHours.objects.filter(service__project__in=project_ids, rendered_by=user)
        .values("service__project", "service__offer")
        .annotate(Sum("hours"))
    ):
        worked_hours_by_offer[row["service__offer"]] += row["hours__sum"]
        worked_hours_by_project[row["service__project"]] += row["hours__sum"]

    def offer_record(offer, planned_works):
        date_from = min(pw["work"]["date_from"] for pw in planned_works)
        date_until = max(pw["work"]["date_until"] for pw in planned_works)
        hours = sum(pw["work"]["planned_hours"] for pw in planned_works)

        return {
            "offer": {
                "date_from": date_from,
                "date_until": date_until,
                "range": "{} – {}".format(
                    local_date_format(date_from, fmt="d.m."),
                    local_date_format(date_until, fmt="d.m."),
                ),
                "planned_hours": hours,
                "worked_hours": Z1,
                **(
                    {
                        "id": offer.id,
                        "title": offer.title,
                        "code": offer.code,
                        "url": offer.get_absolute_url(),
                        "creatework": offer.project.urls["creatework"]
                        + "?offer={}".format(offer.pk),
                        "worked_hours": worked_hours_by_offer[offer.id],
                    }
                    if offer
                    else {}
                ),
            },
            "planned_works": sorted(
                planned_works,
                key=lambda row: (row["work"]["date_from"], row["work"]["date_until"],),
            ),
        }

    def project_record(project, offers):
        offers = sorted(
            (
                offer_record(offer, planned_works)
                for offer, planned_works in sorted(offers.items())
            ),
            key=lambda row: (
                row["offer"]["date_until"],
                row["offer"]["date_from"],
                -row["offer"]["planned_hours"],
            ),
        )

        date_from = min(rec["offer"]["date_from"] for rec in offers)
        date_until = max(rec["offer"]["date_until"] for rec in offers)
        hours = sum(rec["offer"]["planned_hours"] for rec in offers)

        return {
            "project": {
                "id": project.id,
                "title": project.title,
                "code": project.code,
                "url": project.get_absolute_url(),
                "creatework": project.urls["creatework"],
                "date_from": date_from,
                "date_until": date_until,
                "range": "{} – {}".format(
                    local_date_format(date_from, fmt="d.m."),
                    local_date_format(date_until, fmt="d.m."),
                ),
                "planned_hours": hours,
                "worked_hours": worked_hours_by_project[project.id],
            },
            "by_week": [by_project_and_week[project][week] for week in weeks],
            "offers": offers,
        }

    return {
        "weeks": [
            {
                "month": local_date_format(week, fmt="F"),
                "day": local_date_format(week, fmt="d."),
            }
            for week in weeks
        ],
        "projects_offers": sorted(
            [
                project_record(project, offers)
                for project, offers in projects_offers.items()
            ],
            key=lambda row: (
                row["project"]["date_until"],
                row["project"]["date_from"],
                -row["project"]["planned_hours"],
            ),
        ),
        "by_week": [by_week[week] for week in weeks],
    }


def project_planning(project):
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """\
WITH sq AS (
    SELECT unnest(weeks) AS week
    FROM planning_plannedwork
    WHERE project_id=%s

    UNION ALL

    SELECT earliest_start_on AS week
    FROM planning_planningrequest
    WHERE project_id=%s

    UNION ALL

    SELECT completion_requested_on AS week
    FROM planning_planningrequest
    WHERE project_id=%s
)
SELECT MIN(week), MAX(week) FROM sq
            """,
            [project.id, project.id, project.id],
        )
        result = list(cursor)[0]

    if result[0]:
        weeks = list(
            islice(
                recurring(monday(), "weekly"), 2 + (result[1] - result[0]).days // 7,
            )
        )
    else:
        weeks = list(islice(recurring(monday(), "weekly"), 52))

    by_week = defaultdict(lambda: Z1)
    offers = defaultdict(list)

    for pw in PlannedWork.objects.filter(
        project=project, weeks__overlap=weeks
    ).select_related("project__owned_by", "offer__project", "offer__owned_by", "user"):
        per_week = (pw.planned_hours / len(pw.weeks)).quantize(Z2)
        for week in pw.weeks:
            by_week[week] += per_week

        date_from = min(pw.weeks)
        date_until = max(pw.weeks) + dt.timedelta(days=6)

        offers[pw.offer].append(
            {
                "work": {
                    "id": pw.id,
                    "title": "{} ({})".format(pw.title, pw.user.get_short_name()),
                    "planned_hours": pw.planned_hours,
                    "url": pw.get_absolute_url(),
                    "date_from": date_from,
                    "date_until": date_until,
                    "range": "{} – {}".format(
                        local_date_format(date_from, fmt="d.m."),
                        local_date_format(date_until, fmt="d.m."),
                    ),
                },
                "hours_per_week": [
                    per_week if week in pw.weeks else Z1 for week in weeks
                ],
            }
        )

    for pr in PlanningRequest.objects.filter(project=project).select_related(
        "project__owned_by", "offer__project", "offer__owned_by"
    ):
        date_from = pr.earliest_start_on
        date_until = pr.completion_requested_on - dt.timedelta(days=1)

        requested_weeks = (pr.completion_requested_on - date_from).days // 7
        per_week = (pr.requested_hours / requested_weeks).quantize(Z2)

        offers[pr.offer].append(
            {
                "work": {  # FIXME
                    "id": pr.id,
                    "title": "{}: {}".format(_("Request"), pr.title),
                    "requested_hours": pr.requested_hours,
                    "planned_hours": pr.planned_hours,
                    "missing_hours": pr.requested_hours - pr.planned_hours,
                    "url": pr.get_absolute_url(),
                    "date_from": date_from,
                    "date_until": date_until,
                    "range": "{} – {}".format(
                        local_date_format(date_from, fmt="d.m."),
                        local_date_format(date_until, fmt="d.m."),
                    ),
                },
                "hours_per_week": [
                    per_week if date_from < week < date_until else Z1 for week in weeks
                ],
            }
        )

    worked_hours_by_offer = defaultdict(lambda: Z1)
    worked_hours = Z1
    for row in (
        LoggedHours.objects.filter(service__project=project)
        .values("service__offer")
        .annotate(Sum("hours"))
    ):
        worked_hours_by_offer[row["service__offer"]] += row["hours__sum"]
        worked_hours += row["hours__sum"]

    def offer_record(offer, planned_works):
        date_from = min(pw["work"]["date_from"] for pw in planned_works)
        date_until = max(pw["work"]["date_until"] for pw in planned_works)
        hours = sum(pw["work"]["planned_hours"] for pw in planned_works)

        return {
            "offer": {
                "date_from": date_from,
                "date_until": date_until,
                "range": "{} – {}".format(
                    local_date_format(date_from, fmt="d.m."),
                    local_date_format(date_until, fmt="d.m."),
                ),
                "planned_hours": hours,
                "worked_hours": Z1,
                **(
                    {
                        "id": offer.id,
                        "title": offer.title,
                        "code": offer.code,
                        "url": offer.get_absolute_url(),
                        "creatework": offer.project.urls["creatework"]
                        + "?offer={}".format(offer.pk),
                        "worked_hours": worked_hours_by_offer[offer.id],
                    }
                    if offer
                    else {}
                ),
            },
            "planned_works": sorted(
                planned_works,
                key=lambda row: (row["work"]["date_from"], row["work"]["date_until"],),
            ),
        }

    def project_record(project, offers):
        offers = sorted(
            (
                offer_record(offer, planned_works)
                for offer, planned_works in sorted(offers.items())
            ),
            key=lambda row: (
                row["offer"]["date_until"],
                row["offer"]["date_from"],
                -row["offer"]["planned_hours"],
            ),
        )

        date_from = min(rec["offer"]["date_from"] for rec in offers)
        date_until = max(rec["offer"]["date_until"] for rec in offers)
        hours = sum(rec["offer"]["planned_hours"] for rec in offers)

        return {
            "project": {
                "id": project.id,
                "title": project.title,
                "code": project.code,
                "url": project.get_absolute_url(),
                "creatework": project.urls["creatework"],
                "date_from": date_from,
                "date_until": date_until,
                "range": "{} – {}".format(
                    local_date_format(date_from, fmt="d.m."),
                    local_date_format(date_until, fmt="d.m."),
                ),
                "planned_hours": hours,
                "worked_hours": worked_hours,
            },
            "by_week": [by_week[week] for week in weeks],
            "offers": offers,
        }

    return {
        "weeks": [
            {
                "month": local_date_format(week, fmt="F"),
                "day": local_date_format(week, fmt="d."),
            }
            for week in weeks
        ],
        "projects_offers": sorted(
            [project_record(project, offers)] if offers else [],
            key=lambda row: (
                row["project"]["date_until"],
                row["project"]["date_from"],
                -row["project"]["planned_hours"],
            ),
        ),
        "by_week": [by_week[week] for week in weeks],
    }


def test():  # pragma: no cover
    from pprint import pprint

    # from workbench.accounts.models import User
    # pprint(user_planning(User.objects.get(pk=1)))
    from workbench.projects.models import Project

    pprint(project_planning(Project.objects.get(pk=8238)))
