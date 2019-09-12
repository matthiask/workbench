import datetime as dt

from django.core.exceptions import ValidationError


def monday(day=None):
    day = day or dt.date.today()
    return day - dt.timedelta(days=day.weekday())


def raise_if_errors(errors, exclude=None):
    if errors:
        if set(exclude or ()) & errors.keys():
            raise ValidationError(", ".join(str(e) for e in errors.values()))
        raise ValidationError(errors)
