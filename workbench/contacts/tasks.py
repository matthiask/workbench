import datetime as dt

from django.conf import settings
from django.utils import timezone
from requests import HTTPError, api

from workbench.audit.models import LoggedAction
from workbench.contacts.models import EmailAddress, Person


def upload_contacts_to_brevo():
    # Determine persons that need to be updated. Get machting emails
    # and addresses
    since = timezone.now().replace(hour=0, minute=0, second=0)
    since -= dt.timedelta(days=1)

    person_ids = {
        int(row.row_data["id"])
        for row in LoggedAction.objects.filter(
            created_at__gte=since, table_name=Person._meta.db_table, action="I"
        )
    }

    person_ids |= {
        int(row.row_data["person_id"])
        for row in LoggedAction.objects.filter(
            created_at__gte=since, table_name=EmailAddress._meta.db_table, action="I"
        )
    }

    persons_to_sync = Person.objects.active().filter(id__in=person_ids)

    emails = {
        obj.person_id: obj
        for obj in EmailAddress.objects.filter(person__in=persons_to_sync).order_by(
            "-weight", "-id"
        )
    }

    # Update person by person
    for person in persons_to_sync:
        email = emails.get(person.id)

        # Skip all persons that don't have an email
        if not email:
            continue

        logged_action = LoggedAction.objects.get(
            table_name=Person._meta.db_table, row_data__id=person.id, action="I"
        )

        if not logged_action:
            continue

        forward_data = {
            "email": email.email,
            "given_name": person.given_name,
            "family_name": person.family_name,
            "salutation": person.address,
            "full_salutation": person.salutation,
            "primary_contact": person.primary_contact.get_full_name(),
            "created_at": str(logged_action.created_at),
            "groups": ", ".join([g.title for g in person.groups.all()]),
        }

        # send to brevo
        try:
            api.post(settings.BREVO_WEBHOOK_URL, json=forward_data)
        except HTTPError as err:
            print(err)
