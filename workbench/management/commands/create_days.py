from datetime import date

from django.core.management import BaseCommand

from workbench.accounts.middleware import set_user_name
from workbench.calendar.holidays import get_public_holidays
from workbench.calendar.models import App, PublicHoliday


class Command(BaseCommand):
    def handle(self, **options):
        set_user_name("Hangar")
        year = date.today().year

        for day, name in get_public_holidays(year).items():
            PublicHoliday.objects.get_or_create(day=day, defaults={"name": name})
        for day, name in get_public_holidays(year + 1).items():
            PublicHoliday.objects.get_or_create(day=day, defaults={"name": name})

        for app in App.objects.all():
            app.create_days(year=year)
            app.create_days(year=year + 1)
