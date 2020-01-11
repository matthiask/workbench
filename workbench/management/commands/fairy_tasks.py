from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.accounts.middleware import set_user_name
from workbench.invoices.tasks import create_recurring_invoices_and_notify
from workbench.reporting.accounting import send_accounting_files
from workbench.reporting.tasks import create_accruals_for_last_month


class Command(BaseCommand):
    help = "Fairy tasks"

    def handle(self, **options):
        activate("de")
        set_user_name("Fairy tasks")
        create_accruals_for_last_month()
        create_recurring_invoices_and_notify()
        send_accounting_files()
