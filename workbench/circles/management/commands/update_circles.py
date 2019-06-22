from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.accounts.middleware import set_user_name
from workbench.circles.tasks import update_circles


class Command(BaseCommand):
    help = "Update circles"

    def handle(self, **options):
        activate("de")
        set_user_name("GlassFrog")
        update_circles()
