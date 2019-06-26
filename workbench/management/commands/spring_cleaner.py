import re
from html.parser import HTMLParser

from django.core.management.base import BaseCommand

from workbench.accounts.middleware import set_user_name
from workbench.accounts.models import User
from workbench.contacts.models import PostalAddress
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.invoices.utils import recurring
from workbench.offers.models import Offer
from workbench.projects.models import Project


class _DeHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.__text = []

    def handle_data(self, data):
        text = data.strip()
        if len(text) > 0:
            text = re.sub("[ \t\r\n]+", " ", text)
            self.__text.append(text + " ")

    def handle_entityref(self, name):
        self.__text.append(self.unescape("&%s;" % name))

    def handle_charref(self, name):
        self.__text.append(self.unescape("&#%s;" % name))

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.__text.append("\n\n")
        elif tag == "br":
            self.__text.append("\n")
        elif tag == "li":
            self.__text.append("\n- ")

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.__text.append("\n\n")

    def text(self):
        return "".join(self.__text).strip()


def dehtml(text):
    try:
        parser = _DeHTMLParser()
        parser.feed(text)
        parser.close()
        return parser.text()
    except Exception:
        return text


class Command(BaseCommand):
    help = "De-htmlizes description fields"

    def handle(self, **options):
        set_user_name("Frühlingsputz")

        self.stdout.write("updating street and house numbers...")
        for postal_address in PostalAddress.objects.order_by("street"):
            if (
                re.search(r"\b[0-9]+$", postal_address.street)
                and not postal_address.house_number
            ):
                two = postal_address.street.rsplit(" ", 1)
                if len(two) == 2:
                    postal_address.street, postal_address.house_number = two
                    postal_address.save()

        self.stdout.write("updating employments' until dates...")
        for user in User.objects.all():
            employment = user.employments.last()
            if employment:
                employment.save()
                if not employment.percentage:
                    employment.delete()

        self.stdout.write("updating recurring invoices' next_period_starts_on dates...")
        for invoice in RecurringInvoice.objects.filter(
            next_period_starts_on__isnull=False
        ):
            dates = recurring(invoice.next_period_starts_on, invoice.periodicity)
            next(dates)
            invoice.next_period_starts_on = next(dates)
            invoice.save()

        RecurringInvoice.objects.create_invoices()

        self.stdout.write("dehtmling invoices...")
        for instance in Invoice.objects.all():
            instance.description = dehtml(instance.description)
            instance.postal_address = instance.postal_address.strip()
            instance.save(update_fields=("description",))

        self.stdout.write("dehtmling offers...")
        for instance in Offer.objects.all():
            instance.description = dehtml(instance.description)
            instance.postal_address = instance.postal_address.strip()
            instance.save(update_fields=("description",))

        self.stdout.write("dehtmling projects...")
        for instance in Project.objects.all():
            instance.description = dehtml(instance.description)
            instance.save(update_fields=("description",))
