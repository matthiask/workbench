import datetime as dt

from workbench.planning.holidays import get_public_holidays, get_zurich_holidays
from workbench.planning.models import PublicHoliday


def create_public_holidays():
    year = dt.date.today().year

    days = get_zurich_holidays()
    for i in range(year, year + 3):
        days |= get_public_holidays(i)

    for day, (name, fraction) in days.items():
        if year <= day.year < year + 3:
            PublicHoliday.objects.get_or_create(
                date=day,
                defaults={"name": name, "fraction": fraction},
            )
