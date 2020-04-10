from django.core.management.base import BaseCommand

from workbench.contacts.tasks import upload_changes_to_mailchimp


class Command(BaseCommand):
    help = "Synchronize mailchimp mailing list"

    def handle(self, **options):
        upload_changes_to_mailchimp()
