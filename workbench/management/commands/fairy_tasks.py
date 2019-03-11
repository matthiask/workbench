from collections import defaultdict

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.utils.translation import activate, gettext as _

from workbench.accounts.middleware import set_user_name
from workbench.invoices.models import RecurringInvoice
from workbench.templatetags.workbench import currency
from workbench.tools.formats import local_date_format


class Command(BaseCommand):
    help = "Fairy tasks"

    def handle(self, **options):
        activate("de")
        set_user_name("Fairy tasks")

        by_owner = defaultdict(list)
        for invoice in RecurringInvoice.objects.create_invoices():
            by_owner[invoice.owned_by].append(invoice)

        for owner, invoices in by_owner.items():
            invoices = "\n".join(
                "{} {} {}\n{}{}\n".format(
                    invoice,
                    currency(invoice.total),
                    local_date_format(invoice.invoiced_on, "d.m.Y"),
                    settings.WORKBENCH.URL,
                    invoice.get_absolute_url(),
                )
                for invoice in invoices
            )
            mail = EmailMultiAlternatives(
                _("recurring invoices"), invoices, to=[owner.email]
            )
            mail.send()
