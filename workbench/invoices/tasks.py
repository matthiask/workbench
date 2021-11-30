import datetime as dt
from collections import defaultdict

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import gettext as _

from workbench.invoices.models import RecurringInvoice
from workbench.invoices.utils import next_valid_day
from workbench.reporting.key_data import unsent_projected_invoices
from workbench.tools.formats import currency, local_date_format


TEMPLATE = """\
{base_url}{recurring_url} ==>
{customer}
{invoiced_on}
{invoice}
{total}
{base_url}{invoice_url}

"""


def create_recurring_invoices_and_notify():
    by_owner = defaultdict(list)
    for ri in RecurringInvoice.objects.renewal_candidates():
        for invoice in ri.create_invoices():
            by_owner[invoice.owned_by].append((ri, invoice))

    for owner, invoices in by_owner.items():
        invoices = "\n".join(
            TEMPLATE.format(
                invoice=invoice,
                customer=invoice.contact.name_with_organization
                if invoice.contact
                else invoice.customer,
                total=currency(invoice.total),
                invoiced_on=local_date_format(invoice.invoiced_on),
                base_url=settings.WORKBENCH.URL,
                invoice_url=invoice.get_absolute_url(),
                recurring_url=ri.get_absolute_url(),
            )
            for (ri, invoice) in invoices
        )
        mail = EmailMultiAlternatives(
            _("recurring invoices"),
            invoices,
            to=[owner.email],
            cc=["workbench@feinheit.ch"],
        )
        mail.send()


PROJECTED_INVOICES_TEMPLATE = """\
{project}
{base_url}{project_url}
Delta: {unsent}
"""


def send_unsent_projected_invoices_reminders():
    today = dt.date.today()
    next_month = next_valid_day(today.year, today.month, 99)
    if (next_month - today).days != 3:  # third-last day of month
        return

    upi = unsent_projected_invoices(next_month)
    by_user = defaultdict(list)

    for project in upi:
        by_user[project["project"].owned_by].append(project)

    for user, projects in by_user.items():
        body = "\n\n".join(
            PROJECTED_INVOICES_TEMPLATE.format(
                project=project["project"],
                base_url=settings.WORKBENCH.URL,
                project_url=project["project"].get_absolute_url(),
                unsent=currency(project["unsent"]),
            )
            for project in projects
        )
        eom = local_date_format(next_month - dt.timedelta(days=1))
        EmailMultiAlternatives(
            "{} ({})".format(_("Unsent projected invoices"), eom),
            f"""\
Hallo {user}

Das geplante Rechnungstotal per {eom} wurde bei
folgenden Projekten noch nicht erreicht:

{body}

Wenn Du die Rechnungen nicht stellen kannst, aktualisiere bitte
die geplanten Rechnungen oder schliesse das Projekt.
""",
            to=[user.email],
            cc=["workbench@feinheit.ch"],
        ).send()
