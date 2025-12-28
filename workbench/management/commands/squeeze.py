import argparse
import datetime as dt
import io
import re
from collections import defaultdict
from decimal import Decimal
from itertools import chain

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.db.models import Q, Sum
from django.utils.translation import activate, gettext as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.awt.reporting import employment_percentages
from workbench.awt.utils import monthly_days
from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import InternalType, InternalTypeUser, Project, Service
from workbench.projects.reporting import hours_per_type
from workbench.tools.formats import Z0, Z1, Z2, local_date_format
from workbench.tools.xlsx import WorkbenchXLSXDocument


EXPECTED_AVERAGE_HOURLY_RATE = Decimal(150)
WORKING_TIME_PER_DAY = Decimal(8)
WORKING_DAYS_PER_YEAR = Decimal(250)
DAYS_PER_YEAR = Decimal("365.24")


def working_days_estimation(date_range):
    days = (date_range[1] - date_range[0]).days + 1
    return days * WORKING_DAYS_PER_YEAR / DAYS_PER_YEAR


def range_type(arg_value):
    if matches := re.match(r"(\d{4})(\d{2})(\d{2})-(\d{4})(\d{2})(\d{2})", arg_value):
        groups = [int(group) for group in matches.groups()]
        return [dt.date(*groups[:3]), dt.date(*groups[3:])]
    raise argparse.ArgumentTypeError("invalid value")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--last-month",
            action="store_true",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=None,
        )
        parser.add_argument(
            "--range",
            type=range_type,
            help="Specify as YYYYMMDD-YYYYMMDD",
        )
        parser.add_argument(
            "--mailto",
            type=str,
        )

    def handle(self, **options):  # noqa: C901
        activate("de")

        last_month_end = dt.date.today().replace(day=1) - dt.timedelta(days=1)
        date_range = options["range"] or (
            [
                dt.date(options["year"], 1, 1),
                min(last_month_end, dt.date(options["year"], 12, 31)),
            ]
            if options["year"]
            else [
                dt.date(last_month_end.year, 1, 1),
                min(last_month_end, dt.date(last_month_end.year, 12, 31)),
            ]
        )

        if options["last_month"]:
            date_range = [
                date_range[1].replace(day=1),
                date_range[1],
            ]

        if date_range[0] >= date_range[1]:
            self.stderr.write("Date range empty.")
            return

        projects = defaultdict(
            lambda: {
                "invoiced": Z2,
                "projected": Z2,
                "offered": Z2,
                "hours_logged": Z1,
                "hours_offered": Z1,
                "hours_in_range_by_user": {},
            }
        )
        users = defaultdict(
            lambda: {
                "margin": Z2,
                "hours_in_range": Z1,
            }
        )
        user_dict = {u.id: u for u in User.objects.all()}

        logged = (
            LoggedHours.objects
            .filter(rendered_on__range=date_range)
            .order_by()
            .values("rendered_by", "service__project")
            .annotate(Sum("hours"))
        )
        for row in logged:
            p = projects[row["service__project"]]
            u = user_dict[row["rendered_by"]]

            p["hours_in_range_by_user"][u] = row["hours__sum"]
            users[u]["hours_in_range"] += row["hours__sum"]

        total_hours = (
            LoggedHours.objects
            .order_by()
            .filter(service__project__in=projects.keys())
            .values("service__project")
            .annotate(Sum("hours"))
        )
        for row in total_hours:
            projects[row["service__project"]]["hours_logged"] = row["hours__sum"]

        offered_hours = (
            Service.objects
            .order_by()
            .budgeted()
            .filter(project__in=projects.keys(), project__closed_on__isnull=True)
            .values("project")
            .annotate(Sum("service_hours"))
        )
        for row in offered_hours:
            projects[row["project"]]["hours_offered"] = row["service_hours__sum"]

        invoiced_per_project = (
            Invoice.objects
            .invoiced()
            .filter(project__in=projects.keys())
            .order_by()
            .values("project")
            .annotate(Sum("total_excl_tax"), Sum("third_party_costs"))
        )
        for row in invoiced_per_project:
            projects[row["project"]]["invoiced"] = (
                row["total_excl_tax__sum"] - row["third_party_costs__sum"]
            )

        # Subtract third party costs from logged costs which have not been
        # invoiced yet. Maybe we're double counting here but I'd rather have a
        # pessimistic outlook here.
        for row in (
            LoggedCost.objects
            .filter(
                service__project__in=projects.keys(),
                third_party_costs__isnull=False,
                invoice_service__isnull=True,
            )
            .order_by()
            .values("service__project")
            .annotate(Sum("third_party_costs"))
        ):
            projects[row["service__project"]]["invoiced"] -= row[
                "third_party_costs__sum"
            ]

        for pi in ProjectedInvoice.objects.filter(
            project__in=projects.keys(), project__closed_on__isnull=True
        ):
            projects[pi.project_id]["projected"] += pi.gross_margin

        offers = Offer.objects.accepted().filter(
            project__in=projects.keys(), project__closed_on__isnull=True
        )
        for offer in offers:
            projects[offer.project_id]["offered"] += offer.total_excl_tax
        for row in (
            Service.objects
            .filter(offer__in=offers, third_party_costs__isnull=False)
            .order_by()
            .values("project")
            .annotate(Sum("third_party_costs"))
        ):
            projects[row["project"]]["offered"] -= row["third_party_costs__sum"]

        for project_id, project in Project.objects.in_bulk(projects.keys()).items():
            projects[project_id]["project"] = project

        all_users = sorted(users.keys())
        ep = employment_percentages()

        def average_percentage(user):
            percentages = []
            for month in recurring(date_range[0], "monthly"):
                if month > date_range[1]:
                    break
                percentages.append(ep[user].get(month, Z0))
            return sum(percentages, Z0) / len(percentages)

        body = f"Squeeze {local_date_format(date_range[0])} - {local_date_format(date_range[1])}"
        header = [[body]]

        projects_table = [
            [
                _("project"),
                _("offered (only open projects)"),
                _("projected gross margin (only open projects)"),
                _("invoiced without third party costs"),
                _("relevant gross margin"),
                _("offered hours (only open projects)"),
                _("logged hours"),
                _("relevant hours"),
                _("rate"),
                *list(chain.from_iterable((str(u), "") for u in all_users)),
            ],
            [
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                *list(
                    chain.from_iterable(
                        (_("hours"), _("gross margin")) for _u in all_users
                    )
                ),
            ],
            *sorted(
                (project_row(row, all_users, users=users) for row in projects.values()),
                key=lambda row: row[4],
                reverse=True,
            ),
        ]

        hpt = hours_per_type(date_range, users=users.keys())
        hptu = {row["user"]: row for row in hpt["users"]}

        all_users_margin = sum(row["margin"] for row in users.values())
        all_users_hours_in_range = sum(row["hours_in_range"] for row in users.values())

        user_internal_types = defaultdict(dict)
        for m2m in InternalTypeUser.objects.select_related("internal_type"):
            user_internal_types[m2m.user_id][m2m.internal_type] = m2m
        types = list(InternalType.objects.all())

        absence_days_per_user = defaultdict(lambda: Decimal(1))
        for absence in Absence.objects.filter(
            Q(ends_on__isnull=True, starts_on__range=date_range)
            | (
                Q(ends_on__isnull=False)
                & Q(starts_on__lte=date_range[1], ends_on__gte=date_range[0])
            ),
            Q(
                reason__in=[
                    # Vacations are always included (XXX even if too many days!)
                    Absence.VACATION,
                    # It would be nice to count sickness, but ...
                    # Absence.SICKNESS,
                    # Include paid absences since some of them are paid for by the state
                    Absence.PAID,
                    # Include school attendance of apprentices
                    Absence.SCHOOL,
                    # Don't include other absences (no working time), otherwise we'd also
                    # have to subtract if people do too much work
                    # Absence.OTHER,
                ]
            )
            | Q(
                # Include working time corrections (unpaid leaves)
                reason=Absence.CORRECTION,
                days__gt=0,
            ),
        ).select_related("user"):
            months = list(
                monthly_days(absence.starts_on, absence.ends_on or absence.starts_on)
            )
            absence_day_per_period_day = absence.days / sum(m[1] for m in months)
            for month, days in months:
                if date_range[0] <= month <= date_range[1]:
                    absence_days_per_user[absence.user] += (
                        days * absence_day_per_period_day
                    )

        def user_expectation(user, row, employment_percentage):
            internal_percentages = [
                -user_internal_types[user.id][type].percentage
                if type in user_internal_types[user.id]
                else 0
                for type in types
            ]
            profitable_percentage = 100 + sum(internal_percentages)
            external_percentage = 100 * hptu[user]["external"] / hptu[user]["total"]
            expected_gross_margin = (
                EXPECTED_AVERAGE_HOURLY_RATE
                * WORKING_TIME_PER_DAY
                * (working_days_estimation(date_range) - absence_days_per_user[user])
                * Decimal(profitable_percentage)
                / 100
                * Decimal(employment_percentage)
                / 100
            )
            delta = row["margin"] - expected_gross_margin

            return [p or None for p in internal_percentages] + [
                profitable_percentage,
                external_percentage,
                external_percentage - profitable_percentage,
                expected_gross_margin,
                delta,
            ]

        users_table = [
            [
                _("user"),
                _("specialist field"),
                _("employment percentage YTD"),
                _("relevant gross margin"),
                _("relevant hours"),
                _("rate"),
                "",
                _("internal hours"),
                _("external hours"),
                _("total hours"),
                "",
                _("invoiced per external hour"),
                "",
                _("starting point"),
            ]
            + [type.name for type in types]
            + [
                _("Target value: external percentage"),
                _("external percentage"),
                "",
                _("Target value: gross margin"),
                "",
                _("included absence days"),
            ],
            [
                _("Total"),
                "",
                sum((average_percentage(user) for user in all_users), Z0),
                all_users_margin,
                all_users_hours_in_range,
                all_users_margin / all_users_hours_in_range,
                "",
                hpt["total"]["internal"],
                hpt["total"]["external"],
                hpt["total"]["total"],
                "",
                all_users_margin
                / all_users_hours_in_range
                / (1 - hpt["total"]["internal"] / hpt["total"]["total"]),
                "",
                "",
            ]
            + ["" for _type in types]
            + [
                "",
                100 * hpt["total"]["external"] / hpt["total"]["total"],
                _("Delta"),
                _("Target value w/ {}/h").format(EXPECTED_AVERAGE_HOURLY_RATE),
                _("Delta"),
                "",
            ],
            [],
            *sorted(
                (
                    [
                        user,
                        user.specialist_field.name
                        if user.specialist_field
                        else _("<unknown>"),
                        average_percentage(user),
                        row["margin"],
                        row["hours_in_range"],
                        row["margin"] / row["hours_in_range"],
                        "",
                        hptu[user]["internal"],
                        hptu[user]["external"],
                        hptu[user]["total"],
                        "",
                        row["margin"]
                        / row["hours_in_range"]
                        / (1 - hptu[user]["internal"] / hptu[user]["total"])
                        if hptu[user]["external"]
                        else 0,
                        "",
                        100,
                        *user_expectation(user, row, average_percentage(user)),
                        absence_days_per_user[user],
                    ]
                    for user, row in users.items()
                ),
                key=lambda row: row[-2],
                reverse=True,
            ),
        ]

        fields = defaultdict(lambda: {"margin": Z2, "hours_in_range": Z1, "names": []})
        for user, row in users.items():
            field = (
                user.specialist_field.name if user.specialist_field else "<unbekannt>"
            )
            fields[field]["margin"] += row["margin"]
            fields[field]["hours_in_range"] += row["hours_in_range"]
            fields[field]["names"].append(str(user))

        fields_table = [
            [
                _("specialist field"),
                _("users"),
                _("relevant gross margin"),
                _("relevant hours"),
                _("rate"),
            ],
            *sorted(
                (
                    [
                        name,
                        ", ".join(sorted(row["names"])),
                        row["margin"],
                        row["hours_in_range"],
                        row["margin"] / row["hours_in_range"]
                        if row["hours_in_range"]
                        else 0,
                    ]
                    for name, row in fields.items()
                ),
                key=lambda row: row[-1],
                reverse=True,
            ),
        ]

        organizations = defaultdict(lambda: {"margin": Z2, "hours_in_range": Z1})
        for project_id, project_data in projects.items():
            if "project" in project_data:
                project = project_data["project"]
                org_name = str(project.customer)

                margin = max((
                    project_data["offered"],
                    project_data["projected"],
                    project_data["invoiced"],
                ))
                hours = max((
                    project_data["hours_offered"],
                    project_data["hours_logged"],
                ))

                if hours:
                    for user, user_hours in project_data[
                        "hours_in_range_by_user"
                    ].items():
                        user_margin = user_hours / hours * margin
                        organizations[org_name]["margin"] += user_margin
                        organizations[org_name]["hours_in_range"] += user_hours

        organizations_table = [
            [
                _("organization"),
                _("relevant gross margin"),
                _("relevant hours"),
                _("rate"),
            ],
            *sorted(
                (
                    [
                        name,
                        row["margin"],
                        row["hours_in_range"],
                        row["margin"] / row["hours_in_range"]
                        if row["hours_in_range"]
                        else 0,
                    ]
                    for name, row in organizations.items()
                ),
                key=lambda row: row[-1],
                reverse=True,
            ),
        ]

        xlsx = WorkbenchXLSXDocument()
        xlsx.add_sheet(_("users").replace(":", "_"))
        xlsx.table(None, header + users_table)
        xlsx.add_sheet(_("specialist fields"))
        xlsx.table(None, header + fields_table)
        xlsx.add_sheet(_("organizations"))
        xlsx.table(None, header + organizations_table)
        xlsx.add_sheet(_("projects"))
        xlsx.table(None, header + projects_table)

        filename = f"squeeze-{date_range[0]}-{date_range[1]}.xlsx"

        if options["mailto"]:
            mail = EmailMultiAlternatives(
                "Squeeze",
                body,
                to=options["mailto"].split(","),
                reply_to=options["mailto"].split(","),
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


def project_row(row, all_users, *, users):
    margin = max((row["offered"], row["projected"], row["invoiced"]))
    hours = max((row["hours_offered"], row["hours_logged"]))

    def user_cells(u):
        if by_user := row["hours_in_range_by_user"].get(u):
            user_margin = by_user / hours * margin
            users[u]["margin"] += user_margin
            return (by_user, user_margin)
        return ("", "")

    return [
        row["project"],
        row["offered"],
        row["projected"],
        row["invoiced"],
        margin,
        row["hours_offered"],
        row["hours_logged"],
        hours,
        margin / hours,
        *list(chain.from_iterable(user_cells(u) for u in all_users)),
    ]
