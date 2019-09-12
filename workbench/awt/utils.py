import datetime as dt
from calendar import isleap


def days_per_month(year):
    return [31, 29 if isleap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def monthly_days(date_from, date_until):
    month = date_from.replace(day=1)
    while True:
        next_month = month + dt.timedelta(
            days=days_per_month(month.year)[month.month - 1]
        )
        if month < date_from and next_month > date_until:
            yield (month, (date_until - date_from).days + 1)
            break
        if month < date_from:
            yield (month, (next_month - date_from).days)
        elif next_month > date_until:
            yield (month, (date_until - month).days + 1)
            break
        else:
            yield (month, (next_month - month).days)
        month = next_month
