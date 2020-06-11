from collections import defaultdict

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import gettext as _

from workbench.invoices.models import RecurringInvoice
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
            _("recurring invoices"), invoices, to=[owner.email], bcc=settings.BCC
        )
        mail.send()
