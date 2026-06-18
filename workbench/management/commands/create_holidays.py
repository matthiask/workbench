from django.conf import settings
from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.accounts.middleware import set_user_name
from workbench.awt.tasks import create_holidays


class Command(BaseCommand):
    help = "Create holidays"

    def handle(self, **options):
        activate(settings.WORKBENCH.PDF_LANGUAGE)
        set_user_name("Holidays creator")
        create_holidays()
