from datetime import date

from django.core.management import BaseCommand

from workbench.accounts.middleware import set_user_name
from workbench.calendar.models import App


class Command(BaseCommand):
    def handle(self, **options):
        set_user_name("Hangar")
        year = date.today().year
        for app in App.objects.all():
            app.create_days(year=year)
            app.create_days(year=year + 1)
