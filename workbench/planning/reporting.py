import datetime as dt
from collections import defaultdict
from itertools import islice, takewhile

from django.db import connections
from django.db.models import Q, Sum

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.contacts.models import Organization
from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedHours
from workbench.planning.models import Milestone, PlannedWork
from workbench.services.models import ServiceType
from workbench.tools.formats import Z1, Z2, local_date_format
from workbench.tools.reporting import query
from workbench.tools.validation import monday


def _period(weeks, min, max):
    try:
        start = weeks.index(min)
    except ValueError:
        start = 0

    try:
        end = weeks.index(max)
    except ValueError:
        end = len(weeks) - 1

    return [start, end]


class Planning:
    def __init__(self, *, weeks, users=None):
        self.weeks = weeks
        self.users = users

        self._by_week = defaultdict(lambda: Z1)
        self._by_project_and_week = defaultdict(lambda: defaultdict(lambda: Z1))
        self._projects_offers = defaultdict(lambda: defaultdict(list))
        self._project_ids = set()
        self._user_ids = {user.id for user in users} if users else set()

        self._worked_hours = defaultdict(lambda: defaultdict(lambda: Z1))

        self._absences = defaultdict(lambda: [0] * len(weeks))
        self._milestones = defaultdict(lambda: defaultdict(list))

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
                        "id": pw.id,
                        "title": pw.title,
                        "text": pw.user.get_short_name(),
                        "user": pw.user.get_short_name(),
                        "planned_hours": pw.planned_hours,
                        "url": pw.get_absolute_url(),
                        "date_from": date_from,
                        "date_until": date_until,
                        "range": "{} – {}".format(
                            local_date_format(date_from, fmt="d.m."),
                            local_date_format(date_until, fmt="d.m."),
                        ),
                        "service_type_id": pw.service_type_id,
                        "is_provisional": pw.is_provisional,
                    },
                    "hours_per_week": [
                        per_week if week in pw.weeks else Z1 for week in self.weeks
                    ],
                    "per_week": per_week,
                }
            )

            self._project_ids.add(pw.project.pk)
            self._user_ids.add(pw.user.id)

    def add_worked_hours(self, queryset):
        for row in (
            queryset.filter(service__project__in=self._project_ids)
            .values("service__project", "service__offer", "rendered_on")
            .annotate(Sum("hours"))
        ):
            self._worked_hours[row["service__project"]][
                monday(row["rendered_on"])
            ] += row["hours__sum"]

    def add_absences(self, queryset):
        for absence in queryset.filter(
            Q(user__in=self._user_ids),
            Q(starts_on__lte=max(self.weeks)),
            Q(ends_on__isnull=False, ends_on__gte=min(self.weeks))
            | Q(ends_on__isnull=True, starts_on__gte=min(self.weeks)),
        ).select_related("user"):
            date_from = monday(absence.starts_on)
            date_until = monday(absence.ends_on or absence.starts_on)
            hours = absence.days * absence.user.planning_hours_per_day
            weeks = [
                (idx, week)
                for idx, week in enumerate(self.weeks)
                if date_from <= week <= date_until
            ]

            for idx, week in weeks:
                self._absences[absence.user][idx] += hours / len(weeks)
                self._by_week[week] += hours / len(weeks)

    def add_milestones(self, queryset):
        for milestone in queryset.filter(project__in=self._project_ids).select_related(
            "project"
        ):
            self._milestones[milestone.project][monday(milestone.date)].append(
                {
                    "id": milestone.id,
                    "title": milestone.title,
                    "dow": local_date_format(milestone.date, fmt="l, j.n."),
                    "date": local_date_format(milestone.date, fmt="j."),
                    "weekday": milestone.date.isocalendar()[2],
                    "url": milestone.urls["detail"],
                }
            )

    def _offer_record(self, offer, work_list):
        date_from = min(pw["work"]["date_from"] for pw in work_list)
        date_until = max(pw["work"]["date_until"] for pw in work_list)
        hours = sum(pw["work"]["planned_hours"] for pw in work_list)

        if not work_list:
            return None

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
                        "is_declined": offer.is_declined,
                        "is_accepted": offer.is_accepted,
                        "url": offer.get_absolute_url(),
                        "creatework": offer.project.urls["creatework"]
                        + "?offer={}".format(offer.pk),
                    }
                    if offer
                    else {}
                ),
            },
            "work_list": sorted(
                work_list,
                key=lambda row: (row["work"]["date_from"], row["work"]["date_until"]),
            ),
        }

    def _project_record(self, project, offers):
        offers = sorted(
            filter(
                None,
                (
                    self._offer_record(offer, work_list)
                    for offer, work_list in sorted(offers.items())
                ),
            ),
            key=lambda row: (
                row["offer"]["date_from"],
                row["offer"]["date_until"],
                -row["offer"]["planned_hours"],
            ),
        )

        if not offers:
            return None

        date_from = min(rec["offer"]["date_from"] for rec in offers)
        date_until = max(rec["offer"]["date_until"] for rec in offers)
        hours = sum(rec["offer"]["planned_hours"] for rec in offers)

        milestones = [self._milestones[project][week] for week in self.weeks]

        return {
            "project": {
                "id": project.id,
                "title": project.title,
                "is_closed": bool(project.closed_on),
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
                "worked_hours": [
                    self._worked_hours[project.id][week] for week in self.weeks
                ],
                "milestones": milestones if any(milestones) else None,
            },
            "by_week": [
                self._by_project_and_week[project][week] for week in self.weeks
            ],
            "offers": offers,
        }

    def capacity(self):
        by_user = defaultdict(dict)
        total = defaultdict(int)

        user_ids = (
            [user.id for user in self.users] if self.users else list(self._user_ids)
        )

        for week, user, capacity in query(
            """
select
    week,
    user_id,
    coalesce(percentage, 0) * 5 * coalesce(planning_hours_per_day, 0) / 100
        - coalesce(pw_hours, 0)
        - coalesce(abs_hours, 0) as capacity

--
-- Determine the employment percentage and planning_hours_per_day
-- for each user and week
--
from generate_series(%s::date, %s::date, '7 days') as week
left outer join lateral (
    select
        user_id,
        date_from,
        date_until,
        percentage,
        planning_hours_per_day
    from awt_employment
    left join accounts_user on awt_employment.user_id=accounts_user.id
    where user_id = any (%s)
) as employment
on employment.date_from <= week and employment.date_until > week

--
-- Aggregate planned hours per week, distributing equally the planned_hours
-- value over all weeks in the planned work record
--
left outer join lateral (
    select
        user_id as pw_user_id,
        sum(planned_hours / cardinality(weeks)) as pw_hours,
        unnest(weeks) as pw_week
    from planning_plannedwork
    where user_id = any (%s)
    group by pw_user_id, pw_week
) as planned
on week=pw_week and user_id=pw_user_id

left outer join lateral(

    --
    -- Generate rows of absences (user_id, days, planning_hours, weeks::date[])
    --
    with sq as (
        select
            user_id as abs_user_id,
            days,
            planning_hours_per_day,
            (
              select array_agg(w::date) from generate_series(
                date_trunc('week', starts_on),
                date_trunc('week', ends_on),
                '7 days'
              ) as w
            ) as weeks
          from awt_absence
          where user_id = any(%s)
          and user_id=employment.user_id
          and employment.date_from <= date_trunc('week', week)
          and employment.date_until > date_trunc('week', week)
    )
    --
    -- Calculate the planning hours for each absence and distribute the hours
    -- over all weeks in which the absence takes place
    --
    select
      abs_user_id,
      sum(days * planning_hours_per_day / cardinality(weeks)) as abs_hours,
      unnest(weeks) as abs_week
    from sq
    group by abs_user_id, abs_week

) as absences
on week=abs_week and user_id=abs_user_id
            """,
            [min(self.weeks), max(self.weeks), user_ids, user_ids, user_ids],
        ):
            by_user[user][week.date()] = capacity
            total[week.date()] += capacity

        users = self.users or list(User.objects.filter(id__in=by_user))
        return {
            "total": [total.get(week, 0) for week in self.weeks],
            "by_user": [
                {
                    "user": {
                        "name": user.get_full_name(),
                        "url": user.urls["planning"],
                    },
                    "capacity": [by_user[user.id].get(week, 0) for week in self.weeks],
                }
                for user in sorted(users)
            ],
        }

    def report(self):
        try:
            this_week_index = self.weeks.index(monday())
        except ValueError:
            this_week_index = None
        return {
            "this_week_index": this_week_index,
            "weeks": [
                {
                    "monday": week,
                    "month": local_date_format(week, fmt="M"),
                    "week": local_date_format(week, fmt="W"),
                    "period": "{}–{}".format(
                        local_date_format(week, fmt="j."),
                        local_date_format(week + dt.timedelta(days=6), fmt="j."),
                    ),
                }
                for week in self.weeks
            ],
            "projects_offers": sorted(
                filter(
                    None,
                    (
                        self._project_record(project, offers)
                        for project, offers in self._projects_offers.items()
                    ),
                ),
                key=lambda row: (
                    row["project"]["date_from"],
                    row["project"]["date_until"],
                    -row["project"]["planned_hours"],
                ),
            ),
            "by_week": [self._by_week[week] for week in self.weeks],
            "absences": [
                (str(user), lst) for user, lst in sorted(self._absences.items())
            ],
            "capacity": self.capacity() if self.users else None,
            "service_types": [
                {"id": type.id, "title": type.title, "color": type.color}
                for type in ServiceType.objects.all()
            ],
        }


def user_planning(user, date_range):
    start, end = date_range
    weeks = list(takewhile(lambda x: x <= end, recurring(monday(start), "weekly")))
    planning = Planning(weeks=weeks, users=[user])
    planning.add_planned_work(user.planned_work.all())
    planning.add_worked_hours(user.loggedhours.all())
    planning.add_absences(user.absences.all())
    planning.add_milestones(Milestone.objects.all())
    return planning.report()


def team_planning(team, date_range):
    start, end = date_range
    weeks = list(takewhile(lambda x: x <= end, recurring(monday(start), "weekly")))
    planning = Planning(weeks=weeks, users=list(team.members.active()))
    planning.add_planned_work(PlannedWork.objects.filter(user__teams=team))
    planning.add_worked_hours(LoggedHours.objects.filter(rendered_by__teams=team))
    planning.add_absences(Absence.objects.filter(user__teams=team))
    planning.add_milestones(Milestone.objects.all())
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

    SELECT date_trunc('week', date)::date
    FROM planning_milestone
    WHERE project_id=%s
)
SELECT MIN(week), MAX(week) FROM sq
            """,
            [project.id, project.id],
        )
        result = list(cursor)[0]

    if result[0]:
        result = (min(result[0], monday() - dt.timedelta(days=14)), result[1])
        weeks = list(
            islice(
                recurring(result[0], "weekly"),
                2 + (result[1] - result[0]).days // 7,
            )
        )
    else:
        weeks = list(islice(recurring(monday() - dt.timedelta(days=14), "weekly"), 80))

    planning = Planning(weeks=weeks)
    planning.add_planned_work(project.planned_work.all())
    planning.add_worked_hours(LoggedHours.objects.all())
    planning.add_absences(Absence.objects.all())
    planning.add_milestones(Milestone.objects.all())
    return planning.report()


def planning_vs_logbook(date_range, *, users):
    planned = defaultdict(dict)
    logged = defaultdict(dict)

    user_ids = [user.id for user in users]

    seen_weeks = set()

    for customer_id, week, hours in query(
        """
with
planned_per_week as (
    select
        p.customer_id,
        unnest(weeks) as week,
        planned_hours / array_length(weeks, 1) / 5 as hours
    from planning_plannedwork pw
    left join projects_project p on pw.project_id = p.id
    where user_id = any(%s)
),
weeks as (
    select
        date_trunc('week', day) as week,
        count(*) as days
    from generate_series(%s::date, %s::date, '1 day') as day
    where extract(dow from day) between 1 and 5
    group by week
)

select
    customer_id,
    weeks.week,
    sum(hours * weeks.days)
from
    planned_per_week, weeks
where
    planned_per_week.week = weeks.week
group by customer_id, weeks.week
        """,
        [user_ids, *date_range],
    ):
        seen_weeks.add(week)
        planned[customer_id][week] = hours

    for customer_id, week, hours in query(
        """
select
    p.customer_id,
    date_trunc('week', rendered_on) as week,
    sum(hours) as hours
from logbook_loggedhours lh
left join projects_service ps on lh.service_id = ps.id
left join projects_project p on ps.project_id = p.id
where
    rendered_by_id = any(%s)
    and rendered_on between %s::date and %s::date
group by customer_id, week
        """,
        [user_ids, *date_range],
    ):
        seen_weeks.add(week)
        logged[customer_id][week] = hours

    customers = {
        customer.id: customer
        for customer in Organization.objects.filter(
            id__in=planned.keys() | logged.keys()
        )
    }
    weeks = sorted(seen_weeks)

    def _customer(planned, logged):
        ret = [
            {
                "customer": customers[customer_id],
                "per_week": [
                    {
                        "week": week,
                        "planned": planned[customer_id].get(week),
                        "logged": logged[customer_id].get(week),
                    }
                    for week in weeks
                ],
                "planned": sum(planned[customer_id].values(), Z1),
                "logged": sum(logged[customer_id].values(), Z1),
            }
            for customer_id in planned.keys() | logged.keys()
        ]
        return sorted(ret, key=lambda row: -row["planned"])

    ret = {
        "per_customer": _customer(planned, logged),
        "weeks": weeks,
    }
    ret["planned"] = sum((c["planned"] for c in ret["per_customer"]), Z1)
    ret["logged"] = sum((c["logged"] for c in ret["per_customer"]), Z1)
    return ret


def test():  # pragma: no cover
    from pprint import pprint

    if False:
        from workbench.accounts.models import User

        pprint(user_planning(User.objects.get(pk=1)))

    if False:
        from workbench.accounts.models import Team

        pprint(team_planning(Team.objects.get(pk=1)))

    if False:
        from workbench.projects.models import Project

        pprint(project_planning(Project.objects.get(pk=8238)))

    if True:
        from workbench.accounts.models import User

        pprint(
            planning_vs_logbook(
                [dt.date(2021, 1, 1), dt.date.today()],
                users=[User.objects.get(pk=1)],
            )
        )
