import datetime as dt
from decimal import Decimal

from django.utils.formats import date_format
from django.utils.timezone import localtime


H1 = Decimal("0.0")
H2 = Decimal("0.00")


def local_date_format(dttm, fmt=None):
    if not dttm:
        return ""
    if hasattr(dttm, "astimezone"):
        dttm = localtime(dttm)
    return date_format(
        dttm, fmt or ("d.m.Y H:i" if isinstance(dttm, dt.datetime) else "d.m.Y")
    )


def currency(value, show_plus_sign=False):
    if value:
        value = value.quantize(H2)
    return (
        "{}{:,.2f}".format("+" if show_plus_sign and value > 0 else "", value).replace(
            ",", "’"
        )
        if value
        else "0.00"
    )


def days(value):
    if value:
        value = value.quantize(H2)
    return "{:,.2f}d".format(value).replace(",", "’") if value else "0.00d"


def hours(value):
    if value:
        value = value.quantize(H1)
    return "{:,.1f}h".format(value).replace(",", "’") if value else "0.0h"
