import datetime as dt

from django.core.management import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date

from workbench.credit_control.reporting import paid_debtors_zip
from workbench.invoices.models import Invoice
from workbench.reporting.models import FreezeDate


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=dt.date.today().year,
            help="The year for which to export debtors (defaults to %(default)s)",
        )
        parser.add_argument("target", type=str)
        parser.add_argument("--archive", type=str)
        parser.add_argument("--qr", action="store_true")

    def handle(self, **options):
        if a := options["archive"]:
            archive = parse_date(a)
            if not archive:
                raise CommandError(f"Invalid archive value {a!r}")
        else:
            self.stdout.write(
                "--archive argument not provided, not archiving anything."
            )

        date_range = [dt.date(options["year"], 1, 1), dt.date(options["year"], 12, 31)]
        with open(options["target"], "wb") as f:
            paid_debtors_zip(date_range, file=f, qr=options["qr"])

        if a:
            updated = (
                Invoice.objects.filter(
                    invoiced_on__lte=archive, archived_at__isnull=True
                )
                .exclude(status=Invoice.IN_PREPARATION)
                .update(archived_at=timezone.now())
            )

            FreezeDate.objects.create(up_to=a)

            self.stdout.write(f"Archived {updated} invoices.")
