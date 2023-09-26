import datetime as dt
import io
from collections import defaultdict
from itertools import chain, takewhile

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.awt.reporting import employment_percentages
from workbench.invoices.utils import recurring
from workbench.planning.models import PlannedWork, PublicHoliday
from workbench.tools.formats import Z1
from workbench.tools.validation import monday
from workbench.tools.xlsx import WorkbenchXLSXDocument


def weeks_range(start, end):
    end = end or start
    return list(takewhile(lambda x: x <= end, recurring(monday(start), "weekly")))


def hours_per_week_for_absence(absence):
    hours = absence.days * absence.user.planning_hours_per_day
    weeks = weeks_range(absence.starts_on, absence.ends_on)
    return {week: hours / len(weeks) for week in weeks}


def hours_per_week_for_planned_work(pw):
    return {week: pw.planned_hours / len(pw.weeks) for week in pw.weeks}


def chainify(iterable):
    return list(chain.from_iterable(iterable))


def average_workload(workloads):
    if None in workloads:
        return None
    return sum(workloads) / len(workloads)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--mailto",
            type=str,
        )

    def handle(self, **options):
        users = (
            User.objects.active()
            .select_related("specialist_field")
            .order_by("specialist_field", "_full_name")
        )
        specialist_field_users = defaultdict(list, {None: []})
        for user in users:
            specialist_field_users[user.specialist_field].append(user)

        start = monday()
        end = start + dt.timedelta(days=7 * 26)
        weeks = list(takewhile(lambda x: x <= end, recurring(start, "weekly")))

        hours_per_week_and_user = defaultdict(
            lambda: defaultdict(
                lambda: {
                    "internal": Z1,
                    "external": Z1,
                    "absences": Z1,
                }
            )
        )

        for absence in Absence.objects.filter(user__in=users).select_related("user"):
            for week, hours in hours_per_week_for_absence(absence).items():
                hours_per_week_and_user[week][absence.user]["absences"] += hours

        for pw in PlannedWork.objects.filter(user__in=users).select_related(
            "project", "user"
        ):
            type = "internal" if pw.project.type == pw.project.INTERNAL else "external"
            for week, hours in hours_per_week_for_planned_work(pw).items():
                hours_per_week_and_user[week][pw.user][type] += hours

        ep = employment_percentages(until_year=end.year)
        for ph in PublicHoliday.objects.filter(date__range=[start, end]):
            week = monday(ph.date)
            month = ph.date.replace(day=1)
            for user in users:
                hours_per_week_and_user[week][user]["absences"] += (
                    ph.fraction * ep[user][month] / 100 * user.planning_hours_per_day
                )

        for user in users:
            if internal := 8 - user.planning_hours_per_day:
                for week in weeks:
                    month = week.replace(day=1)
                    hours_per_week_and_user[week][user]["internal"] += (
                        5 * ep[user][month] / 100 * internal
                    )

        user_table = [
            [
                _("user"),
                _("specialist field"),
                *chainify([week, "", "", ""] for week in weeks),
            ],
            [
                "",
                "",
                *chainify(
                    [_("workload"), _("external"), _("internal"), _("absences")]
                    for week in weeks
                ),
            ],
        ]

        def _user_week_workload(week, user):
            hours = hours_per_week_and_user[week][user]
            month = week.replace(day=1)
            return [
                100 * sum(hours.values()) / (5 * ep[user][month] * 8)
                if ep[user][month]
                else None,
                hours["external"],
                hours["internal"],
                hours["absences"],
            ]

        for user in users:
            user_table.append(
                [
                    user,
                    user.specialist_field,
                    *chainify(_user_week_workload(week, user) for week in weeks),
                ]
            )

        sf_table = [
            [
                _("specialist field"),
                _("users"),
                *chainify([week, "", "", ""] for week in weeks),
            ],
            [
                "",
                "",
                *chainify(
                    [_("workload"), _("external"), _("internal"), _("absences")]
                    for week in weeks
                ),
            ],
        ]

        def _sf_week_workload(week, sf, users):
            hours = [hours_per_week_and_user[week][user] for user in users]
            month = week.replace(day=1)
            eps = sum(5 * ep[user][month] * 8 for user in users)

            external = sum(h["external"] for h in hours)
            internal = sum(h["internal"] for h in hours)
            absences = sum(h["absences"] for h in hours)

            return [
                100 * (external + internal + absences) / eps if eps else None,
                external,
                internal,
                absences,
            ]

        for sf, users in specialist_field_users.items():
            sf_table.append(
                [
                    sf,
                    ", ".join(str(u) for u in users),
                    *chainify(_sf_week_workload(week, sf, users) for week in weeks),
                ]
            )

        xlsx = WorkbenchXLSXDocument()
        xlsx.add_sheet(_("users").replace(":", "_"))
        xlsx.table(None, user_table)
        xlsx.add_sheet(_("specialist fields").replace(":", "_"))
        xlsx.table(None, sf_table)

        group_weeks = 4
        index = 2

        user_grouped_table = [row[0:2] for row in user_table]
        sf_grouped_table = [row[0:2] for row in sf_table]

        while index < len(user_table[2]):
            for row_index, row in enumerate(user_table):
                if row_index == 0:
                    user_grouped_table[0].append(row[index])
                elif row_index == 1:
                    pass
                else:
                    try:
                        workloads = [row[index + i * 4] for i in range(group_weeks)]
                    except IndexError:
                        continue
                    user_grouped_table[row_index].append(average_workload(workloads))

            for row_index, row in enumerate(sf_table):
                if row_index == 0:
                    sf_grouped_table[0].append(row[index])
                elif row_index == 1:
                    pass
                else:
                    try:
                        workloads = [row[index + i * 4] for i in range(group_weeks)]
                    except IndexError:
                        continue
                    sf_grouped_table[row_index].append(average_workload(workloads))

            index += group_weeks * 4

        xlsx.add_sheet(_("user workload"))
        xlsx.table(None, user_grouped_table)
        xlsx.add_sheet(_("specialist fields workload"))
        xlsx.table(None, sf_grouped_table)

        filename = f"workload-{start}--{end}.xlsx"

        if options["mailto"]:
            mail = EmailMultiAlternatives(
                "Workload",
                "",
                to=options["mailto"].split(","),
            )
            with io.BytesIO() as f:
                xlsx.workbook.save(f)
                f.seek(0)
                mail.attach(
                    filename,
                    f.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            mail.send()
        else:
            xlsx.workbook.save(filename)
