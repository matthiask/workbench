import datetime as dt
from collections import defaultdict
from itertools import islice

from django.db import connections
from django.db.models import Q, Sum

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedHours
from workbench.tools.formats import Z1, Z2, local_date_format
from workbench.tools.reporting import query
from workbench.tools.validation import monday


class Planning:
    def __init__(self, *, weeks):
        self.weeks = weeks

        self._by_week = defaultdict(lambda: Z1)
        self._by_project_and_week = defaultdict(lambda: defaultdict(lambda: Z1))
        self._projects_offers = defaultdict(lambda: defaultdict(list))
        self._project_ids = set()
        self._user_ids = set()

        self._worked_hours_by_offer = defaultdict(lambda: Z1)
        self._worked_hours_by_project = defaultdict(lambda: Z1)

        self._absences = defaultdict(lambda: [None] * len(weeks))

    def add_planned_work(self, queryset):
        for pw in queryset.filter(weeks__overlap=self.weeks).select_related(
            "user", "project__owned_by", "offer__project", "offer__owned_by"
        ):
            per_week = (pw.planned_hours / len(pw.weeks)).quantize(Z2)
            for week in pw.weeks:
                self._by_week[week] += per_week
                self._by_project_and_week[pw.project][week] += per_week

            date_from = min(pw.weeks)
            date_until = max(pw.weeks) + dt.timedelta(days=6)

            self._projects_offers[pw.project][pw.offer].append(
                {
                    "work": {
                        "is_request": False,
                        "id": pw.id,
                        "title": pw.title,
                        "user": pw.user.get_short_name(),
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
                        per_week if week in pw.weeks else Z1 for week in self.weeks
                    ],
                }
            )

            self._project_ids.add(pw.project.pk)
            self._user_ids.add(pw.user.id)

    def add_planning_requests(self, queryset):
        for pr in (
            queryset.filter(
                Q(earliest_start_on__lte=max(self.weeks)),
                Q(completion_requested_on__gte=min(self.weeks)),
            )
            .select_related("project__owned_by", "offer__project", "offer__owned_by")
            .prefetch_related("receivers")
        ):
            date_from = min(pr.weeks)
            date_until = max(pr.weeks)
            per_week = (pr.requested_hours / len(pr.weeks)).quantize(Z2)

            self._projects_offers[pr.project][pr.offer].append(
                {
                    "work": {
                        "is_request": True,
                        "id": pr.id,
                        "title": pr.title,
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
                        per_week if week in pr.weeks else Z1 for week in self.weeks
                    ],
                }
            )

            self._project_ids.add(pr.project.pk)
            self._user_ids |= {user.id for user in pr.receivers.all()}

    def add_worked_hours(self, queryset):
        for row in (
            queryset.filter(service__project__in=self._project_ids)
            .values("service__project", "service__offer")
            .annotate(Sum("hours"))
        ):
            self._worked_hours_by_offer[row["service__offer"]] += row["hours__sum"]
            self._worked_hours_by_project[row["service__project"]] += row["hours__sum"]

    def add_absences(self, queryset):
        for absence in queryset.filter(
            Q(user__in=self._user_ids),
            Q(starts_on__lte=max(self.weeks)),
            Q(ends_on__gte=min(self.weeks)),
        ).select_related("user"):
            data = {
                "reason": absence.get_reason_display(),
                "description": absence.description,
                "days": absence.days,
                "url": absence.get_absolute_url(),
            }

            date_from = monday(absence.starts_on)
            date_until = monday(absence.ends_on or absence.starts_on)
            for idx, week in enumerate(self.weeks):
                if date_from <= week <= date_until:
                    self._absences[absence.user][idx] = data

    def _offer_record(self, offer, work_list):
        date_from = min(pw["work"]["date_from"] for pw in work_list)
        date_until = max(pw["work"]["date_until"] for pw in work_list)
        hours = sum(pw["work"]["planned_hours"] for pw in work_list)

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
                        "worked_hours": self._worked_hours_by_offer[offer.id],
                    }
                    if offer
                    else {}
                ),
            },
            "work_list": sorted(
                work_list,
                key=lambda row: (row["work"]["date_from"], row["work"]["date_until"],),
            ),
        }

    def _project_record(self, project, offers):
        offers = sorted(
            (
                self._offer_record(offer, work_list)
                for offer, work_list in sorted(offers.items())
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
                "planning": project.urls["planning"],
                "creatework": project.urls["creatework"],
                "date_from": date_from,
                "date_until": date_until,
                "range": "{} – {}".format(
                    local_date_format(date_from, fmt="d.m."),
                    local_date_format(date_until, fmt="d.m."),
                ),
                "planned_hours": hours,
                "worked_hours": self._worked_hours_by_project[project.id],
            },
            "by_week": [
                self._by_project_and_week[project][week] for week in self.weeks
            ],
            "offers": offers,
        }

    def capacity(self):
        by_user = defaultdict(dict)
        total = defaultdict(int)

        for week, user, percentage in query(
            """
select week, user_id, percentage
from generate_series(%s::date, %s::date, '7 days') as week
left outer join lateral (
    select * from awt_employment where user_id = any (%s)
) as employment
on employment.date_from <= week and employment.date_until > week
            """,
            [min(self.weeks), max(self.weeks), list(self._user_ids)],
        ):
            by_user[user][week.date()] = percentage
            total[week.date()] += percentage

        users = list(User.objects.filter(id__in=by_user))
        return {
            "total": [total.get(week, 0) for week in self.weeks],
            "by_user": [
                {
                    "user": user,
                    "capacity": [by_user[user.id].get(week, 0) for week in self.weeks],
                }
                for user in sorted(users)
            ],
        }

    def report(self):
        # from pprint import pprint
        # pprint(self.capacity())

        return {
            "weeks": [
                {
                    "month": local_date_format(week, fmt="F"),
                    "day": local_date_format(week, fmt="d."),
                }
                for week in self.weeks
            ],
            "projects_offers": sorted(
                [
                    self._project_record(project, offers)
                    for project, offers in self._projects_offers.items()
                ],
                key=lambda row: (
                    row["project"]["date_until"],
                    row["project"]["date_from"],
                    -row["project"]["planned_hours"],
                ),
            ),
            "by_week": [self._by_week[week] for week in self.weeks],
            "absences": [
                (str(user), lst) for user, lst in sorted(self._absences.items())
            ],
        }


def user_planning(user):
    weeks = list(islice(recurring(monday(), "weekly"), 52))
    planning = Planning(weeks=weeks)
    planning.add_planned_work(user.planned_work.all())
    planning.add_planning_requests(user.received_planning_requests.all())
    planning.add_worked_hours(user.loggedhours.all())
    planning.add_absences(user.absences.all())
    return planning.report()


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

    SELECT completion_requested_on - 7 AS week
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
                recurring(result[0], "weekly"), 2 + (result[1] - result[0]).days // 7,
            )
        )
    else:
        weeks = list(islice(recurring(monday(), "weekly"), 52))

    planning = Planning(weeks=weeks)
    planning.add_planned_work(project.planned_work.all())
    planning.add_planning_requests(project.planning_requests.all())
    planning.add_worked_hours(LoggedHours.objects.all())
    # planning.add_absences(user.absences.all())
    planning.add_absences(Absence.objects.all())
    return planning.report()


def test():  # pragma: no cover
    from pprint import pprint

    # from workbench.accounts.models import User
    # pprint(user_planning(User.objects.get(pk=1)))
    from workbench.projects.models import Project

    pprint(project_planning(Project.objects.get(pk=8238)))
