import datetime as dt
from decimal import Decimal

from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext as _


H1 = Decimal("0.0")
H2 = Decimal("0.00")


def local_date_format(dttm):
    if hasattr(dttm, "astimezone"):
        dttm = localtime(dttm)
    return date_format(dttm, "d.m.Y H:i" if isinstance(dttm, dt.datetime) else "d.m.Y")


def pretty_due(day):
    days = (day - dt.date.today()).days
    if days > 14:
        return _("due in %s weeks") % (days // 7)
    elif days > 1:
        return _("due in %s days") % days
    elif days == 1:
        return _("due tomorrow")
    elif days == 0:
        return _("due today")
    else:
        return _("overdue!")


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
    return ("%.2fd" % value) if value else "0.00d"


def hours(value):
    if value:
        value = value.quantize(H1)
    return ("%.1fh" % value) if value else "0.0h"
