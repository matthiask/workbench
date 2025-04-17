import io
from itertools import chain, takewhile

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.utils.translation import gettext as _

from workbench.invoices.utils import recurring
from workbench.projects.reporting import hours_per_type_distribution
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
        parser.add_argument("year", type=int)
        parser.add_argument(
            "--mailto",
            type=str,
        )

    def handle(self, year, mailto="", **options):
        data = hours_per_type_distribution(year)

        xlsx = WorkbenchXLSXDocument()
        xlsx.add_sheet(_("internal types").replace(":", "_"))
        xlsx.table(None, data)

        filename = f"internal-types-{year}.xlsx"

        if mailto:
            mail = EmailMultiAlternatives(
                _("internal types"),
                "",
                to=mailto.split(","),
                reply_to=mailto.split(","),
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
