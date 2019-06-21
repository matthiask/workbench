from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from mailchimp3 import MailChimp

from workbench.audit.models import LoggedAction
from workbench.contacts.models import EmailAddress, Person, PostalAddress


API_KEY = settings.MAILCHIMP_API_KEY
LIST_ID = settings.MAILCHIMP_LIST_ID  # target list


class Command(BaseCommand):
    help = "Synchronize mailchimp mailing list"

    def handle(self, **options):
        # Determine persons that need to be updated. Get machting emails
        # and addresses
        since = timezone.now().replace(hour=0, minute=0, second=0)
        since -= timedelta(days=1)

        person_ids = {
            int(row.row_data["id"])
            for row in LoggedAction.objects.filter(
                created_at__gte=since, table_name=Person._meta.db_table
            )
        }

        person_ids |= {
            int(row.row_data["person_id"])
            for row in LoggedAction.objects.filter(
                created_at__gte=since, table_name=EmailAddress._meta.db_table
            )
        }

        persons_to_sync = Person.objects.filter(is_archived=False, id__in=person_ids)

        emails = {
            obj.person_id: obj
            for obj in EmailAddress.objects.filter(person__in=persons_to_sync).order_by(
                "weight", "id"
            )
        }
        addresses = {
            obj.person_id: obj
            for obj in PostalAddress.objects.filter(
                person__in=persons_to_sync
            ).order_by("weight", "id")
        }

        print(person_ids)

        client = MailChimp(API_KEY)

        # Update person by person
        for person in persons_to_sync:
            email = emails.get(person.id)

            # Skip all persons that don't have an email
            if not email:
                continue

            print(u"{0} {1}".format(person, email.email).encode("utf-8"))

            # construct merge fields (will be extendend below)
            merge_fields = {
                # "TITLE": person.salutation,
                "FNAME": person.given_name,
                "LNAME": person.family_name,
                "ANREDE": person.salutation,
            }

            # get address
            address = addresses.get(person.id)
            if address:
                if address.postal_address_override:
                    merge_fields["ADDRESS"] = address.postal_address_override
                else:
                    merge_fields["ADDRESS"] = "\n".join(
                        (
                            f
                            for f in (
                                "%s %s" % (address.street, address.house_number),
                                address.address_suffix,
                                "%s %s" % (address.postal_code, address.city),
                                address.country.name
                                if address.country.code != "CH"
                                else "",
                            )
                            if f
                        )
                    )

            # save to mailchimp
            client.lists.members.create_or_update(
                LIST_ID,
                email.email,
                {
                    "email_address": email.email,
                    "status_if_new": "subscribed",
                    "merge_fields": merge_fields,
                },
            )
