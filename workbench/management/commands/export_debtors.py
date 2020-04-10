import datetime as dt
import io

from django.core.management import BaseCommand

from workbench.credit_control.reporting import paid_debtors_zip


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=dt.date.today().year,
            help="The year for which to export debtors (defaults to %(default)s)",
        )
        parser.add_argument("target", type=str)

    def handle(self, **options):
        date_range = [dt.date(options["year"], 1, 1), dt.date(options["year"], 12, 31)]
        with io.open(options["target"], "wb") as f:
            paid_debtors_zip(date_range, file=f)
