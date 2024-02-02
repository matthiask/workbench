import re
from html.parser import HTMLParser

from django.core.management.base import BaseCommand
from invoices.models import Invoice
from offers.models import Offer
from projects.models import Project


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
        for instance in Invoice.objects.all():
            instance.description = dehtml(instance.description)
            instance.save(update_fields=("description",))
        for instance in Offer.objects.all():
            instance.description = dehtml(instance.description)
            instance.save(update_fields=("description",))
        for instance in Project.objects.all():
            instance.description = dehtml(instance.description)
            instance.save(update_fields=("description",))
