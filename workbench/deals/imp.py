import datetime as dt
import os
from functools import lru_cache
from pprint import pprint
from types import SimpleNamespace

from django.utils import timezone

import jellyfish
import pytz
import requests

from workbench.accounts.middleware import set_user_name
from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.deals.models import AttributeGroup, ClosingType, Deal, ValueType


DOMAIN = "feinheitgmbh.pipedrive.com"
TOKEN = os.environ["PIPEDRIVE_TOKEN"]


VALUE_TYPES = ["Beratung & Konzept", "Grafik", "Programmierung"]

SOURCES = [
    "Empfehlung",
    "Google",
    "Massenmedien",
    "FH Projekt gesehen",
    "Kaltakquise",
    "Bestehender Kunde",
    "Persönliches Netzwerk",
    "Simap",
]

SECTORS = [
    "NPO/NGO",
    "Bildung",
    "Kultur",
    "Politik",
    "Medien & Verlage",
    "Behörden & Ämter",
    "Finanzbranche",
    "Konsumgüter & Lifestyleprodukte",
    "KMU's (Ingenieurwesen, IT, Anwaltskanzlei, Buchhandlung etc.)",
    "Verbände & Gewerkschaften",
    "Wirtschaftsprüfer",
    "Versicherungen",
]

WINS = [
    "Pitch in Konkurrenz",
    "Agentur-/Offertenpräsentation in Konkurrenz",
    "Direkte Projektanfrage ohne Konkurrenz",
]
LOSS = ["Preis", "Andere Agentur (Idee)", "Vorgehen", "Sonstiges ..."]


def initial():
    res = SimpleNamespace()
    res.value_types = []

    for i, title in enumerate(VALUE_TYPES):
        res.value_types.append(
            ValueType.objects.create(title=title, position=10 * (i + 1))
        )

    res.sources = []
    group = AttributeGroup.objects.create(title="Quelle", position=10)
    for i, title in enumerate(SOURCES):
        res.sources.append(group.attributes.create(title=title, position=10 * (i + 1)))

    res.sectors = []
    group = AttributeGroup.objects.create(title="Branche", position=20)
    for i, title in enumerate(SECTORS):
        res.sectors.append(group.attributes.create(title=title, position=10 * (i + 1)))

    res.wins = []
    res.loss = []
    for i, title in enumerate(WINS):
        res.wins.append(
            ClosingType.objects.create(
                title=title, represents_a_win=True, position=10 * (i + 1)
            )
        )
    for i, title in enumerate(LOSS):
        res.loss.append(
            ClosingType.objects.create(
                title=title, represents_a_win=False, position=10 * (i + 1 + len(WINS))
            )
        )

    return res


def parse_date(str):
    return timezone.make_aware(dt.datetime.strptime(str, "%Y-%m-%d %H:%M:%S"), pytz.UTC)


def req(path, params):
    params["api_token"] = TOKEN
    return requests.get("https://{}{}".format(DOMAIN, path), params=params).json()


organizations = list(Organization.objects.all())


@lru_cache(maxsize=None)
def get_organization(name):
    return sorted(
        organizations,
        key=lambda org: jellyfish.damerau_levenshtein_distance(name, org.name),
    )[0]


def run_import():
    deals = []
    deals.extend(
        req("/v1/deals", {"start": 0, "limit": 500, "filter_id": 18})["data"] or []
    )
    deals.extend(
        req("/v1/deals", {"start": 500, "limit": 500, "filter_id": 18})["data"] or []
    )
    deals.extend(
        req("/v1/deals", {"start": 1000, "limit": 500, "filter_id": 18})["data"] or []
    )
    # pprint(deals)
    # return

    if False:
        orgmap = {}
        for deal in deals:
            name = deal["org_id"]["name"] if deal["org_id"] else None
            if not name or name in orgmap:
                continue

            orgmap[name] = get_organization(name)

        pprint(orgmap)
        return

    set_user_name("Pipedrive Import")

    for cls in [Deal, AttributeGroup, ClosingType, ValueType]:
        pass

        cls.objects.all().delete()

    res = initial()

    users = {u.email: u for u in User.objects.all()}

    for deal in deals:
        if not deal["org_id"]:
            print("No organization!", deal)
            continue

        row = {
            "title": deal["title"],
            "owned_by": users[deal["user_id"]["email"]],
            "created_at": parse_date(deal["add_time"]),
            "customer": get_organization(deal["org_id"]["name"]),
            "contact": None,
            "value": deal["value"],
            "status": Deal.ACCEPTED if deal["status"] == "won" else Deal.OPEN,
            "probability": Deal.UNKNOWN,
            "closed_on": parse_date(deal["won_time"]) if deal["won_time"] else None,
            "attributes": {},
            "values": {},
        }

        if deal["stage_id"] == 29:  # Sammelbecken
            continue

        elif deal["stage_id"] == 20:
            row["probability"] = Deal.HIGH
            row["decision_expected_on"] = (
                parse_date(deal["rotten_time"]) if deal["rotten_time"] else None
            )

        elif deal["stage_id"] == 23:
            row["decision_expected_on"] = parse_date(
                deal["update_time"]
            ) + dt.timedelta(days=90)

        elif deal["stage_id"] == 15:
            row["probability"] = Deal.NORMAL

        if deal["9ef99f10926f537a6b8fcdba376acff9cf681689"]:
            row["closing_type"] = {
                "56": res.wins[0],
                "57": res.wins[1],
                "58": res.wins[2],
            }[deal["9ef99f10926f537a6b8fcdba376acff9cf681689"]]

        if deal["eb8aeab3ef56871be14d0b84be8231123fdc5ed8"]:
            row["attributes"]["sectors"] = res.sectors[
                int(deal["eb8aeab3ef56871be14d0b84be8231123fdc5ed8"]) - 44
            ]

        if deal["2f4a07c1b43fbe7c4bb32af8ca063193ac600410"]:
            row["values"][
                {
                    "30": res.value_types[2],
                    "31": res.value_types[1],
                    "32": res.value_types[0],
                }[deal["2f4a07c1b43fbe7c4bb32af8ca063193ac600410"]]
            ] = deal["value"]

        if deal["4ee42cb2b9ae3a449812d61ebfffbae5dd47edaa"]:
            row["attributes"]["sources"] = {
                "1": res.sources[0],
                "2": res.sources[1],
                "3": res.sources[2],
                "4": res.sources[3],
                "5": res.sources[4],
                "6": res.sources[5],
                "33": res.sources[6],
                "59": res.sources[7],
            }[deal["4ee42cb2b9ae3a449812d61ebfffbae5dd47edaa"]]

        # XXX deal["lost_reason"]

        attributes = row.pop("attributes")
        values = row.pop("values")

        deal = Deal(**row)
        deal._fts = " ".join(
            str(part)
            for part in [
                deal.code,
                deal.customer.name,
                deal.contact.full_name if deal.contact else "",
            ]
        )
        super(Deal, deal).save()

        for key, value in values.items():
            deal.values.create(type=key, value=value)
        for key, value in attributes.items():
            deal.attributes.add(value)


run_import()
