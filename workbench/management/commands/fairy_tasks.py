from django.core.management import BaseCommand

from workbench.accounts.middleware import set_user_name
from workbench.invoices.models import RecurringInvoice


class Command(BaseCommand):
    help = "Fairy tasks"

    def handle(self, **options):
        set_user_name("Fairy tasks")
        RecurringInvoice.objects.create_invoices()
