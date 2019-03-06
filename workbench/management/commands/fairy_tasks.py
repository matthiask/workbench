from datetime import date

from django.core.management import BaseCommand
from django.db.models import F, Q

from workbench.accounts.middleware import set_user_name
from workbench.invoices.models import RecurringInvoice


class Command(BaseCommand):
    help = "Fairy tasks"

    def handle(self, **options):
        set_user_name("Fairy tasks")
        today = date.today()

        for ri in RecurringInvoice.objects.filter(
            Q(ends_on__isnull=True) | Q(ends_on__gte=F("next_period_starts_on")),
            Q(next_period_starts_on__isnull=True) | Q(next_period_starts_on__lte=today),
        ):
            ri.create_invoices()
