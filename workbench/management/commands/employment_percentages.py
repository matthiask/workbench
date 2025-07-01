import datetime as dt
import io
from itertools import islice

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand

from workbench.awt.reporting import employment_percentages
from workbench.invoices.utils import recurring
from workbench.tools.xlsx import WorkbenchXLSXDocument


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--mailto",
            type=str,
        )

    def handle(self, **options):
        ep = employment_percentages(until_year=dt.date.today().year)

        min_year = min(min(d.keys()) for d in ep.values())
        max_year = max(max(d.keys()) for d in ep.values())

        years = {}

        for month in recurring(min_year, "monthly"):
            if month > max_year:
                break

            d = years.setdefault(month.year, {})

            for user, percentages in ep.items():
                if month in percentages:
                    d.setdefault(user, [None] * 12)[month.month - 1] = percentages[
                        month
                    ]

        months = list(islice(recurring(dt.date(2000, 1, 1), "monthly"), 12))

        xlsx = WorkbenchXLSXDocument()
        for year, users in reversed(years.items()):
            xlsx.add_sheet(str(year))
            xlsx.table(
                [
                    "",
                    *(month.strftime("%B") for month in months),
                ],
                [(user, *percentages) for user, percentages in sorted(users.items())],
            )

        filename = f"employment-percentages-{min_year}--{max_year}.xlsx"

        if options["mailto"]:
            mail = EmailMultiAlternatives(
                "Workload",
                "",
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
