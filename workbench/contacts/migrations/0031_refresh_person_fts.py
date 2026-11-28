import itertools
import re

from django.db import migrations


# Like workbench.contacts.models.HOME_TYPE
HOME_TYPE = re.compile(r"(home|hause|privat)", re.IGNORECASE)


def _postal_address(address, person):
    """Like ``PostalAddress.postal_address`` (migrations have no methods)"""
    if address.postal_address_override:
        return address.postal_address_override
    organization = person.organization
    lines = [
        organization.name
        if organization
        and not organization.is_private_person
        and not HOME_TYPE.search(address.type)
        else "",
        " ".join(filter(None, (person.given_name, person.family_name))),
        address.address_suffix,
        " ".join(filter(None, (address.street, address.house_number))),
        address.post_office_box,
        " ".join(filter(None, (address.postal_code, address.city))),
        address.country.name if address.country.code != "CH" else "",
    ]
    return "\n".join(filter(None, lines))


def forwards(apps, schema_editor):
    """0030 changed postal addresses with ``save(update_fields=...)`` and job
    titles with ``update()``, which doesn't update the search text of their
    people; like ``Person.fts_text()``, which contains the job title now. Only ``_fts`` changes, which the audit log
    ignores; the search vector follows through its trigger."""
    Person = apps.get_model("contacts", "Person")
    people = (
        Person.objects
        .select_related("organization")
        .prefetch_related("phonenumbers", "emailaddresses", "postaladdresses")
        .order_by("pk")
    )
    changed = []
    for person in people.iterator(chunk_size=500):
        fts = " ".join(
            itertools.chain(
                [person.organization.name if person.organization else ""],
                [person.job_title],
                (detail.phone_number for detail in person.phonenumbers.all()),
                (detail.email for detail in person.emailaddresses.all()),
                (
                    _postal_address(detail, person)
                    for detail in person.postaladdresses.all()
                ),
            )
        )
        if fts != person._fts:
            person._fts = fts
            changed.append(person)
    Person.objects.bulk_update(changed, ["_fts"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("contacts", "0030_move_job_titles_and_post_office_boxes")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
