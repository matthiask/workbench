from datetime import date, timedelta

from django.core.exceptions import ValidationError


def monday(day=None):
    day = day or date.today()
    return day - timedelta(days=day.weekday())


def raise_if_errors(errors, exclude=None):
    if errors:
        if set(exclude or ()) & errors.keys():
            raise ValidationError(", ".join(str(e) for e in errors.values()))
        raise ValidationError(errors)
