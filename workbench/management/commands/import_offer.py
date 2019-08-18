import io
import json
import re
from decimal import Decimal
from html.parser import HTMLParser

from django.core.management import BaseCommand
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import activate

from workbench.accounts.middleware import set_user_name
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service


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
    def add_arguments(self, parser):
        parser.add_argument("dump", nargs=1)

    def handle(self, **options):
        activate("de")
        set_user_name("Offer importer")

        with io.open(options["dump"][0]) as f:
            data = json.load(f)

        offers = {}

        contacts = {
            row["pk"]: {
                "customer_id": row["fields"]["employer"],
                "contact_id": row["fields"]["person"],
            }
            for row in data
            if row["model"] == "addressbook.address"
        }
        activities = {
            row["pk"]: row["fields"]
            for row in data
            if row["model"] == "articles.activity"
        }
        articles = {
            row["pk"]: row["fields"]
            for row in data
            if row["model"] == "articles.article"
        }

        def article_name(stuff, pk):
            if stuff[pk]["level"] <= 1:
                return stuff[pk]["name"]
            else:
                return "%s - %s" % (
                    stuff[stuff[pk]["parent"]]["name"],
                    stuff[pk]["name"],
                )

        for row in data:
            if row["model"] == "offers.joboffer":
                if row["pk"] not in offers:
                    offers[row["pk"]] = {
                        "project": Project(
                            title=row["fields"]["name"],
                            description="",
                            owned_by_id=row["fields"]["manager"],
                            type=Project.ORDER,
                            created_at=parse_datetime(row["fields"]["created"]),
                            **contacts[row["fields"]["contact"]]
                        ),
                        "offer": Offer(
                            title=row["fields"]["name"],
                            description=dehtml(row["fields"]["description"]),
                            owned_by_id=row["fields"]["manager"],
                            created_at=parse_datetime(row["fields"]["created"]),
                            offered_on=parse_date(row["fields"]["offer_date"]),
                            status=Offer.OFFERED,
                            postal_address="%s\r\n%s %s\r\n%s\r\n%s %s"
                            % (
                                row["fields"]["offer_company"],
                                row["fields"]["offer_first_name"],
                                row["fields"]["offer_last_name"],
                                row["fields"]["offer_address"],
                                row["fields"]["offer_zip_code"],
                                row["fields"]["offer_city"],
                            ),
                            subtotal=Decimal(row["fields"]["subtotal"]),
                            discount=Decimal(row["fields"]["discount"]),
                            liable_to_vat=True,
                            tax_rate=Decimal(row["fields"]["tax"]),
                            total=Decimal(row["fields"]["total"]),
                        ),
                        "services": [],
                    }

            elif row["model"] == "offers.offeredactivity":
                offers[row["fields"]["joboffer"]]["services"].append(
                    Service(
                        created_at=parse_datetime(row["fields"]["created"]),
                        title=article_name(activities, row["fields"]["activity"]),
                        description=row["fields"]["notes"],
                        position=row["fields"]["ordering"],
                        effort_type=article_name(activities, row["fields"]["activity"]),
                        effort_hours=Decimal(row["fields"]["hours"]),
                        effort_rate=Decimal(row["fields"]["invoicing_hourly_rate"]),
                        is_optional=row["fields"]["optional"],
                    )
                )

            elif row["model"] == "offers.offeredarticle":
                offers[row["fields"]["joboffer"]]["services"].append(
                    Service(
                        created_at=parse_datetime(row["fields"]["created"]),
                        title=article_name(articles, row["fields"]["article"]),
                        description=row["fields"]["notes"],
                        position=1000 + row["fields"]["ordering"],
                        cost=row["fields"]["count"]
                        * Decimal(row["fields"]["cost"])
                        * (1 + Decimal(row["fields"]["commission"]) / 100),
                    )
                )

        for offer in offers.values():
            offer["project"].save()
            offer["offer"].project = offer["project"]
            offer["offer"].save()
            for service in offer["services"]:
                service.project = offer["project"]
                service.offer = offer["offer"]
                service.save(skip_related_model=True)

            offer["offer"].save()
