from datetime import date

from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext as _


def local_date_format(dttm, fmt):
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
