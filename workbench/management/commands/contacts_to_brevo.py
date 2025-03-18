from django.core.management.base import BaseCommand

from workbench.contacts.tasks import upload_contacts_to_brevo


class Command(BaseCommand):
    help = "Send contacts to Brevo"

    def handle(self, **options):
        upload_contacts_to_brevo()
