import datetime as dt
from collections import defaultdict
from itertools import islice, takewhile

from django.db import connections
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.contacts.models import Organization
from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedHours
from workbench.planning.models import ExternalWork, Milestone, PlannedWork
from workbench.projects.models import Project
from workbench.services.models import ServiceType
from workbench.tools.formats import Z1, Z2, hours, local_date_format
from workbench.tools.reporting import query
from workbench.tools.validation import in_days, monday


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
    def __init__(self, *, external_view=False, weeks, users=None, projects=None):
        self.weeks = weeks
        self.users = users

        self.external = external_view

        self._by_week = defaultdict(lambda: Z1)
        self._by_week_provisional = defaultdict(lambda: Z1)
        self._by_project_and_week = defaultdict(lambda: defaultdict(lambda: Z1))
        self._projects_offers = defaultdict(lambda: defaultdict(list))

        self._projects_external_work = defaultdict(list)

        self._project_ids = {project.id for project in projects} if projects else set()
        self._user_ids = {user.id for user in users} if users else set()

        self._worked_hours = defaultdict(lambda: defaultdict(lambda: Z1))

        self._absences = defaultdict(lambda: [[] for i in weeks])
        self._milestones = defaultdict(lambda: defaultdict(defaultdict))

        self._work_ids_users = defaultdict(set)
        self._planned_users_by_week = defaultdict(lambda: [set() for i in weeks])

    def add_planned_work_and_milestones(
        self,
        planned_work_qs,
        milestones_qs,
        external_work_qs=None,
    ):
        if self.external:
            planned_work_qs = planned_work_qs.filter(milestone__isnull=False)
        for pw in planned_work_qs.filter(weeks__overlap=self.weeks).select_related(
            "user",
            "project__owned_by",
            "offer__project",
            "offer__owned_by",
            "milestone",
        ):
            per_week = (pw.planned_hours / len(pw.weeks)).quantize(Z2)
            for week in pw.weeks:
                self._by_week[week] += per_week
                self._by_project_and_week[pw.project][week] += per_week
                if pw.is_provisional:
                    self._by_week_provisional[week] += per_week

            hours_per_week = []
            for week in self.weeks:
                if week in pw.weeks:
                    hours_per_week.append(per_week)
                else:
                    hours_per_week.append(Z1)

            date_from = min(pw.weeks)
            date_until = max(pw.weeks) + dt.timedelta(days=6)

            self._projects_offers[pw.project][pw.offer].append(
                {
                    "work": {
                        "id": pw.id,
                        "title": pw.title,
                        "text": pw.user.get_short_name(),
                        "user": pw.user.get_short_name(),
                        "planned_hours": pw.planned_hours if not self.external else 0,
                        "url": pw.get_absolute_url(),
                        "date_from": date_from,
                        "date_until": date_until,
                        "range": "{} – {}".format(
                            local_date_format(date_from, fmt="d.m."),
                            local_date_format(date_until, fmt="d.m."),
                        ),
                        "service_type_id": pw.service_type_id,
                        "is_provisional": pw.is_provisional,
                        "tooltip": ", ".join(
                            filter(
                                None,
                                (
                                    str(pw.service_type) if pw.service_type else None,
                                    _("%.1fh per week") % per_week,
                                ),
                            )
                        ),
                    },
                    "hours_per_week": hours_per_week,
                }
            )

            self._work_ids_users[pw.id].add(pw.user)

            self.add_project_milestone(pw.project, pw.milestone)
            self._project_ids.add(pw.project.pk)
            self._user_ids.add(pw.user.id)

        if external_work_qs:
            for ew in external_work_qs.filter(weeks__overlap=self.weeks).select_related(
                "milestone", "provided_by"
            ):
                date_from = min(ew.weeks)
                date_until = max(ew.weeks) + dt.timedelta(days=6)

                self._projects_external_work[ew.project].append(
                    {
                        "id": ew.id,
                        "title": ew.title,
                        "provided_by": ew.provided_by.name,
                        "url": ew.get_absolute_url(),
                        "date_from": date_from,
                        "date_until": date_until,
                        "range": "{} – {}".format(
                            local_date_format(date_from, fmt="d.m."),
                            local_date_format(date_until, fmt="d.m."),
                        ),
                        "service_type_id": ew.service_type_id,
                        "tooltip": str(ew.service_type) if ew.service_type else None,
                        "by_week": [1 if w in ew.weeks else 0 for w in self.weeks],
                    }
                )

                self.add_project_milestone(ew.project, ew.milestone)
                self._project_ids.add(ew.project.pk)

        # TODO: hacky, add projects anyway if there are upcoming milestones.
        # There must be a better way.
        if milestones_qs:
            for ms in milestones_qs.filter(
                Q(date__lte=max(self.weeks)) & Q(date__gte=min(self.weeks))
            ):
                self._projects_offers[ms.project].update()
                self._project_ids.add(ms.project.pk)

    def add_project_milestone(self, project, milestone):
        if milestone and (not self._milestones[project][milestone]):
            start = (
                milestone.phase_starts_on
                if milestone.phase_starts_on
                else milestone.date
            )
            weeks = [
                1 if monday(start) <= w <= monday(milestone.date) else 0
                for w in self.weeks
            ]
            graphical_weeks = [
                1 if monday(milestone.date) == w else 0 for w in self.weeks
            ]

            self._milestones[project][milestone].update(
                {
                    "id": milestone.id,
                    "title": milestone.title,
                    "dow": local_date_format(milestone.date, fmt="l, j.n."),
                    "date": local_date_format(milestone.date, fmt="j."),
                    "range": "{} – {}".format(
                        local_date_format(start, fmt="d.m."),
                        local_date_format(milestone.date, fmt="d.m."),
                    )
                    if milestone.phase_starts_on
                    else None,
                    "hours": milestone.estimated_total_hours,
                    "phase_starts_on": start if milestone.phase_starts_on else None,
                    "weekday": milestone.date.isocalendar()[2],
                    "url": milestone.urls["detail"],
                    "weeks": weeks,
                    "graphical_weeks": graphical_weeks,
                }
            )

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
                self._absences[absence.user][idx].append(
                    (
                        hours / len(weeks),
                        f"{absence.get_reason_display()} - {absence.description}",
                        absence.urls["detail"],
                    )
                )
                self._by_week[week] += hours / len(weeks)

    def add_public_holidays(self):
        ud = {user.id: user for user in User.objects.filter(id__in=self._user_ids)}

        for (
            id,
            date,
            name,
            user_id,
            planning_hours_per_day,
            fraction,
            percentage,
        ) in query(
            """
select
    ph.id,
    ph.date,
    ph.name,
    user_id,
    planning_hours_per_day,
    fraction,
    percentage

from planning_publicholiday ph
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
on employment.date_from <= ph.date and employment.date_until > ph.date

where ph.date between %s and %s and user_id is not null
order by ph.date
            """,
            [list(ud.keys()), min(self.weeks), max(self.weeks)],
        ):
            # Skip weekends
            if date.weekday() >= 5:
                continue

            week = monday(date)
            idx = self.weeks.index(week)

            user = ud[user_id]
            ph_hours = (
                (planning_hours_per_day or 0)
                * (fraction or 0)
                * (percentage or 0)
                / 100
            )
            detail = " × ".join(
                (
                    f"{hours(planning_hours_per_day)}/d",
                    f"{percentage}%",
                    f"{fraction}d",
                )
            )
            self._absences[user][idx].append(
                (
                    ph_hours,
                    f"{name} ({detail} = {hours(ph_hours)})",
                    reverse("planning_publicholiday_detail", kwargs={"pk": id}),
                )
            )
            self._by_week[week] += ph_hours

    def add_milestones(self, queryset):
        for milestone in queryset.filter(
            Q(project__in=self._project_ids)
            & Q(date__lte=max(self.weeks))
            & Q(date__gte=min(self.weeks))
        ).select_related("project"):
            if not self._milestones[milestone.project][milestone]:
                self.add_project_milestone(milestone.project, milestone)

    def _offer_record(self, offer, work_list):
        date_from = min(pw["work"]["date_from"] for pw in work_list)
        date_until = max(pw["work"]["date_until"] for pw in work_list)
        hours = sum(pw["work"]["planned_hours"] for pw in work_list)

        if not work_list:
            return None

        for wl in work_list:
            wl.update(
                {
                    "absences": [
                        [a for a in self._absences[user][idx] if h > 0]
                        for idx, h in enumerate(wl["hours_per_week"])
                    ]
                    for user in self._work_ids_users[wl["work"]["id"]]
                }
            )

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
                        + f"?offer={offer.pk}",
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
        offers = (
            sorted(
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
            if offers
            else None
        )

        date_from = min(rec["offer"]["date_from"] for rec in offers) if offers else None
        date_until = (
            max(rec["offer"]["date_until"] for rec in offers) if offers else None
        )
        hours = sum(rec["offer"]["planned_hours"] for rec in offers) if offers else 0

        milestones = sorted(
            self._milestones[project].values(),
            key=lambda v: v["weeks"].index(1) if 1 in v["weeks"] else 0,
        )

        external_work = sorted(
            self._projects_external_work[project],
            key=lambda v: v["by_week"].index(1) if 1 in v["by_week"] else 0,
        )

        if not (offers or any(milestones) or any(external_work)):
            return None

        return {
            "project": {
                "id": project.id,
                "title": project.title,
                "is_closed": bool(project.closed_on),
                "url": project.get_absolute_url(),
                "planning": project.urls["planning"],
                "creatework": project.urls["creatework"],
                "createexternalwork": project.urls["createexternalwork"],
                "date_from": date_from,
                "date_until": date_until,
                "range": "{} – {}".format(
                    local_date_format(date_from, fmt="d.m."),
                    local_date_format(date_until, fmt="d.m."),
                )
                if date_from and date_until
                else None,
                "planned_hours": hours,
                "worked_hours": [
                    self._worked_hours[project.id][week] for week in self.weeks
                ],
                "milestones": milestones if any(milestones) else None,
            },
            "by_week": [
                self._by_project_and_week[project][week] for week in self.weeks
            ],
            "external_work": external_work if any(external_work) else None,
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
        - coalesce(abs_hours, 0)
        - coalesce(ph_days, 0)
          * coalesce(planning_hours_per_day, 0)
          * coalesce(percentage, 0) / 100
        as capacity

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

left outer join lateral(
    select
      date_trunc('week', date) as ph_week,
      sum(fraction) as ph_days
    from planning_publicholiday
    where extract(dow from date) between 1 and 6
    group by ph_week
) as public_holidays
on week=ph_week

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
                )
                if row["project"]["date_from"] and row["project"]["date_until"]
                else (),
            ),
            "by_week": [self._by_week[week] for week in self.weeks],
            "by_week_provisional": [
                self._by_week_provisional[week] for week in self.weeks
            ],
            "absences": [
                (str(user), lst) for user, lst in sorted(self._absences.items())
            ],
            "capacity": self.capacity() if self.users else None,
            "service_types": [
                {"id": type.id, "title": type.title, "color": type.color}
                for type in ServiceType.objects.all()
            ],
            "external_view": self.external,
        }


def user_planning(user, date_range):
    start, end = date_range
    weeks = list(takewhile(lambda x: x <= end, recurring(monday(start), "weekly")))
    planning = Planning(weeks=weeks, users=[user])
    planning.add_planned_work_and_milestones(
        user.planned_work.select_related("service_type"),
        Milestone.objects.filter(
            Q(project__planned_work__user=user) | Q(project__owned_by=user),
            Q(project__closed_on__isnull=True) | Q(project__closed_on__gte=in_days(-7)),
        ),
    )
    planning.add_worked_hours(user.loggedhours.all())
    planning.add_absences(user.absences.all())
    planning.add_public_holidays()
    planning.add_milestones(Milestone.objects.all())
    return planning.report()


def team_planning(team, date_range):
    start, end = date_range
    weeks = list(takewhile(lambda x: x <= end, recurring(monday(start), "weekly")))
    planning = Planning(weeks=weeks, users=list(team.members.active()))
    planning.add_planned_work_and_milestones(
        PlannedWork.objects.filter(user__teams=team).select_related("service_type"),
        Milestone.objects.filter(
            Q(project__planned_work__user__teams=team),
            Q(project__closed_on__isnull=True) | Q(project__closed_on__gte=in_days(-7)),
        ),
    )
    planning.add_worked_hours(LoggedHours.objects.filter(rendered_by__teams=team))
    planning.add_absences(Absence.objects.filter(user__teams=team))
    planning.add_public_holidays()
    planning.add_milestones(Milestone.objects.all())
    return planning.report()


def project_planning(project, external_view=False):
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

    planning = Planning(external_view=external_view, weeks=weeks)
    planning.add_planned_work_and_milestones(
        project.planned_work.select_related("service_type"),
        project.milestones,
        project.external_work.select_related("service_type"),
    )
    if not external_view:
        planning.add_worked_hours(LoggedHours.objects.all())
    planning.add_absences(Absence.objects.all())
    planning.add_public_holidays()
    planning.add_milestones(Milestone.objects.all())
    return planning.report()


def project_planning_external(project):
    return project_planning(project, True)


def planning_vs_logbook(date_range, *, users):
    planned = defaultdict(dict)
    logged = defaultdict(dict)

    user_ids = [user.id for user in users]

    seen_weeks = set()

    for customer_id, week, planned_hours in query(
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
        planned[customer_id][week] = planned_hours

    for customer_id, week, worked_hours in query(
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
        logged[customer_id][week] = worked_hours

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
        return sorted(ret, key=lambda row: (-row["planned"], -row["logged"]))

    ret = {
        "per_customer": _customer(planned, logged),
        "weeks": weeks,
    }
    ret["planned"] = sum((c["planned"] for c in ret["per_customer"]), Z1)
    ret["logged"] = sum((c["logged"] for c in ret["per_customer"]), Z1)
    return ret


def campaign_planning_external(campaign):
    return campaign_planning(campaign, external_view=True)


def campaign_planning(campaign, *, external_view=False):
    projects = Project.objects.filter(campaign=campaign)
    projects_ids = ([project.id for project in projects],)

    with connections["default"].cursor() as cursor:
        cursor.execute(
            """\
WITH sq AS (
    SELECT unnest(weeks) AS week
    FROM planning_plannedwork
    WHERE project_id = ANY %s

    UNION ALL

    SELECT date_trunc('week', date)::date
    FROM planning_milestone
    WHERE project_id = ANY %s
)
SELECT MIN(week), MAX(week) FROM sq
            """,
            [projects_ids, projects_ids],
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

    planning = Planning(weeks=weeks, projects=projects, external_view=external_view)

    planning.add_planned_work_and_milestones(
        PlannedWork.objects.filter(project__campaign=campaign).select_related(
            "service_type"
        ),
        Milestone.objects.filter(project__campaign=campaign),
        ExternalWork.objects.filter(project__campaign=campaign).select_related(
            "service_type"
        ),
    )
    if not external_view:
        planning.add_worked_hours(LoggedHours.objects.all())
    planning.add_absences(Absence.objects.all())
    planning.add_public_holidays()
    planning.add_milestones(Milestone.objects.all())
    return planning.report()


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
