import re

from django.db import migrations


# Spellings and synonyms of the suggested types; other types (e.g. Home
# Mobile, Büro Lausanne) only lose surplus whitespace
SYNONYMS = {
    "Work": [
        "work",
        "arbeit",
        "work phone",
        "phone",
        "telefon",
        "büro",
        "office",
        "direkt",
        "direct",
        "work direkt",
        "work direct",
        "arbeit telefon",
        "arbeit direkt",
    ],
    "Home": ["home", "privat", "private", "zuhause", "zu hause", "home phone"],
    "Mobile": [
        "mobile",
        "mobil",
        "handy",
        "natel",
        "work mobile",
        "mobile work",
        "mobile arbeit",
        "arbeit mobile",
    ],
    "Fax": ["fax", "work fax", "telfax", "telefax"],
}
TYPES = {synonym: type for type, synonyms in SYNONYMS.items() for synonym in synonyms}

# PersonDetail.WEIGHTS at the time of this migration
WEIGHTS = (
    (re.compile(r"mobil", re.IGNORECASE), 30),
    (re.compile(r"(work|arbeit)", re.IGNORECASE), 20),
    (re.compile(r"(home|hause|privat)", re.IGNORECASE), 10),
    (re.compile(r"(organization|firm)", re.IGNORECASE), -100),
)


def normalize(value):
    """Details copied from the organization keep their prefix"""
    value = " ".join(value.split())
    prefix, rest = "", value
    if value.casefold().startswith("organization "):
        prefix, rest = "organization ", value[len("organization ") :]
    return prefix + TYPES.get(rest.casefold(), rest)


def forwards(apps, schema_editor):
    for model in ["EmailAddress", "PhoneNumber", "PostalAddress"]:
        details = apps.get_model("contacts", model).objects
        for value in details.values_list("type", flat=True).distinct():
            if (type := normalize(value)) != value:
                details.filter(type=value).update(
                    type=type,
                    weight=sum(
                        weight for regex, weight in WEIGHTS if regex.search(type)
                    ),
                )


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0025_detail_types"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
