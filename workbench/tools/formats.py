import datetime as dt

from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext as _


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


def currency(value):
    if not value:
        return "0.00"
    return "{:,.2f}".format(value).replace(",", "’")


def days(value):
    if not value:
        return "0.00d"
    return "%.2fd" % value


def hours(value):
    if not value:
        return "0.0h"
    return "%.1fh" % value
