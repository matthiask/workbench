from datetime import date

from django.utils import timezone
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext as _


def local_date_format(dttm, fmt="d.m.Y"):
    if hasattr(dttm, "astimezone"):
        dttm = localtime(dttm)
    return date_format(dttm, fmt)


def pretty_due(day):
    days = (day - date.today()).days
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


def timesince_short(dttm):
    delta = int((timezone.now() - dttm).total_seconds())
    if delta > 86400 * 180:
        return _("%s months ago") % int(delta // (86400 * 365 / 12))
    if delta > 86400 * 14:
        return _("%s weeks ago") % (delta // (86400 * 7))
    if delta > 86400 * 2:
        return _("%s days ago") % (delta // 86400)
    if delta > 7200:
        return _("%s hours ago") % (delta // 3600)
    if delta > 120:
        return _("%s minutes ago") % (delta // 60)
    return _("%s seconds ago") % delta
