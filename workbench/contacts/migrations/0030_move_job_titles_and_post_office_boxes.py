import re

from django.db import migrations


# Only clear cases, the rest is left for review (the people filter
# "missing or incomplete postal address" lists what doesn't print well)
POST_OFFICE_BOX = re.compile(
    r"^(postfach|case postale|casella postale|p\.?\s?o\.?\s?box|postbox)\b",
    re.IGNORECASE,
)
# "Postfach", "Postfach 573"
STREET_POST_OFFICE_BOX = re.compile(
    r"^(postfach|p\.?\s?o\.?\s?box)(\s+\d+)?$", re.IGNORECASE
)
# "Musterweg 20\r\nPostfach", "Beispielgasse 1 / Postfach", "Beispielplatz
# 2Postfach"
STREET_AND_POST_OFFICE_BOX = re.compile(
    r"^(?P<street>.+?\d\w?)[\s,/]*(?P<box>postfach|p\.?\s?o\.?\s?box)$",
    re.IGNORECASE | re.DOTALL,
)
JOB_TITLE = re.compile(
    r"leiter|leitung|geschäftsführ|ceo|cfo|cto|coo|\bhead\b|manager|managing"
    r"|director|direktor|partner|präsident|mitarbeiter|berater|grafiker"
    r"|designer|redaktor|journalist|assistent|sachbearbeiter|spezialist"
    r"|specialist|consultant|officer|inhaber|gründer|founder|owner"
    r"|verantwortlich|koordinator|referent|sprecher|fotograf|dozent|professor"
    r"|\bprof\.|\bdr\.|anwalt|anwält|produzent|entwickler|developer|texter"
    r"|\blead\b|chef|vorsteher|sekretär|delegierte",
    re.IGNORECASE,
)
CARE_OF = re.compile(r"^(c/o|z\.?\s?h)", re.IGNORECASE)
PLACEHOLDER = re.compile(r"^[\W_]*$|^x$", re.IGNORECASE)


def forwards(apps, schema_editor):
    PostalAddress = apps.get_model("contacts", "PostalAddress")
    Person = apps.get_model("contacts", "Person")
    job_titles = dict(
        Person.objects.exclude(job_title="").values_list("pk", "job_title")
    )

    for address in PostalAddress.objects.order_by("pk"):
        changed = set()
        suffix = address.address_suffix.strip()

        if "\n" not in suffix and not address.post_office_box:
            if POST_OFFICE_BOX.match(suffix):
                address.post_office_box, address.address_suffix = suffix, ""
                changed |= {"post_office_box", "address_suffix"}
            elif JOB_TITLE.search(suffix) and not CARE_OF.match(suffix):
                if address.person_id not in job_titles:
                    job_titles[address.person_id] = suffix
                    Person.objects.filter(pk=address.person_id).update(job_title=suffix)
                if job_titles[address.person_id] == suffix:
                    address.address_suffix = ""
                    changed.add("address_suffix")

        street = address.street.strip()
        number = address.house_number.strip()
        # The number of the box if anything, unless it repeats the postal code
        box_number = (
            number if number.isdigit() and number != address.postal_code else ""
        )
        if not address.post_office_box:
            if match := STREET_POST_OFFICE_BOX.match(street):
                address.post_office_box = " ".join(filter(None, (street, box_number)))
                address.street = address.house_number = ""
                changed |= {"post_office_box", "street", "house_number"}
            elif match := STREET_AND_POST_OFFICE_BOX.match(street):
                # The house number is the number of the box then
                address.street = match["street"].strip()
                address.post_office_box = " ".join(
                    filter(None, ("Postfach", box_number))
                )
                if number.isdigit():
                    address.house_number = ""
                changed |= {"post_office_box", "street", "house_number"}

        if (address.post_office_box or address.postal_address_override) and (
            PLACEHOLDER.match(address.street.strip())
            and PLACEHOLDER.match(address.house_number.strip())
            and (address.street or address.house_number)
        ):
            address.street = address.house_number = ""
            changed |= {"street", "house_number"}

        if changed:
            address.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("contacts", "0029_postal_address_post_office_box")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
