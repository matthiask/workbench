import datetime as dt
from decimal import Decimal

from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import ngettext


Z0 = Decimal("0")
Z1 = Decimal("0.0")
Z2 = Decimal("0.00")


def local_date_format(dttm, *, fmt=None):
    if not dttm:
        return ""
    if hasattr(dttm, "astimezone"):
        dttm = localtime(dttm)
    return date_format(
        dttm, fmt or ("d.m.Y H:i" if isinstance(dttm, dt.datetime) else "d.m.Y")
    )


def _fmt(*, fmt, value, exp, plus_sign=False):
    value = value.quantize(exp) if value else exp
    value = value if value != 0 else exp  # Avoid -0.0
    return fmt.format("+" if plus_sign and value > 0 else "", value).replace(",", "’")


def currency(value, plus_sign=False):
    return _fmt(fmt="{}{:,.2f}", value=value, exp=Z2, plus_sign=plus_sign)


def days(value, plus_sign=False):
    return _fmt(fmt="{}{:,.2f}d", value=value, exp=Z2, plus_sign=plus_sign)


def hours(value, plus_sign=False):
    return _fmt(fmt="{}{:,.1f}h", value=value, exp=Z1, plus_sign=plus_sign)


def hours_and_minutes(seconds):
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    parts = [
        (ngettext("%s hour", "%s hours", hours) % hours) if hours else None,
        ngettext("%s minute", "%s minutes", minutes) % minutes,
    ]
    return " ".join(filter(None, parts))
