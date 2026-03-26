import argparse
import datetime as dt
import io
import re

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.reporting.squeeze import build_xlsx, squeeze_data
from workbench.tools.formats import local_date_format


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

    def handle(self, **options):
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

        data = squeeze_data(date_range)
        xlsx = build_xlsx(data)

        filename = f"squeeze-{date_range[0]}-{date_range[1]}.xlsx"
        body = f"Squeeze {local_date_format(date_range[0])} - {local_date_format(date_range[1])}"

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
