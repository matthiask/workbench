import datetime as dt

from django.core.management import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from workbench.reporting.models import FreezeDate


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--last-month",
            action="store_true",
        )
        parser.add_argument("--day", type=str)

    def handle(self, day, last_month, **kwargs):
        if day and not (day := parse_date(day)):
            raise CommandError(f"Invalid date value {day!r}")
        if not day and last_month:
            day = dt.date.today().replace(day=1) - dt.timedelta(days=1)
        FreezeDate.objects.create(up_to=day)
