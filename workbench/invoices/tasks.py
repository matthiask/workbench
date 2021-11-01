import datetime as dt
from collections import defaultdict

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import gettext as _

from workbench.invoices.models import RecurringInvoice
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
    if dt.date.today().day != 1:
        return

    projects = unsent_projected_invoices()
    by_user = defaultdict(list)

    for project in unsent_projected_invoices():
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
        EmailMultiAlternatives(
            _("Unsent projected invoices"),
            f"""\
Hallo {user}

Das geplante Rechnungstotal wurde bei folgenden Projekten nicht erreicht:

{body}
""",
            to=[user.email],
            cc=["workbench@feinheit.ch"],
        ).send()
