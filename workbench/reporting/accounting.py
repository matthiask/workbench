import datetime as dt
import io

from django.core.mail import EmailMessage

from workbench.accounts.models import User
from workbench.accruals.models import Accrual
from workbench.projects.models import Project
from workbench.projects.reporting import project_budget_statistics
from workbench.tools.xlsx import WorkbenchXLSXDocument


def send_accounting_files():
    today = dt.date.today()
    if (today.day, today.month) != (1, 1):
        return

    xlsx = WorkbenchXLSXDocument()
    xlsx.project_budget_statistics(project_budget_statistics(Project.objects.open()))
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
