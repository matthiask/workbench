import datetime as dt
import io

from django.core.mail import EmailMessage
from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.accounts.middleware import set_user_name
from workbench.accounts.models import User
from workbench.accruals.models import Accrual
from workbench.accruals.tasks import create_accruals_for_last_month
from workbench.invoices.tasks import create_recurring_invoices_and_notify
from workbench.projects.models import Project
from workbench.projects.reporting import project_budget_statistics
from workbench.tools.xlsx import WorkbenchXLSXDocument


class Command(BaseCommand):
    help = "Fairy tasks"

    def handle(self, **options):
        activate("de")
        set_user_name("Fairy tasks")
        create_accruals_for_last_month()
        create_recurring_invoices_and_notify()

        self.send_accounting_files()

    def send_accounting_files(self):
        today = dt.date.today()

        if (today.day, today.month) != (1, 1):
            return

        xlsx = WorkbenchXLSXDocument()
        xlsx.project_budget_statistics(
            project_budget_statistics(Project.objects.open())
        )
        xlsx.accruals(Accrual.objects.filter(cutoff_date=today - dt.timedelta(days=1)))

        mail = EmailMessage(
            "Accounting files",
            to=list(
                User.objects.filter(is_active=True, is_admin=True).values_list(
                    "email", flat=True
                )
            ),
        )
        with io.BytesIO() as buf:
            xlsx.workbook.save(buf)
            mail.attach(
                "accounting.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument." "spreadsheetml.sheet",
            )
        mail.send()
