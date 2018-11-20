from datetime import date
from markdown2 import markdown
import lxml.html
import lxml.html.clean

from django.utils.formats import date_format
from django.utils.html import mark_safe
from django.utils.timezone import localtime
from django.utils.translation import ugettext as _


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


def markdownify(text):
    html = markdown(
        text, extras=["code-friendly", "fenced-code-blocks", "cuddled-lists"]
    )
    html = html.replace("<img", '<img class="img-responsive"')
    doc = lxml.html.fromstring(html)
    cleaner = lxml.html.clean.Cleaner(
        scripts=False, style=False, remove_tags=("script", "style")
    )
    cleaner(doc)
    html = lxml.html.tostring(doc, method="xml").decode("utf-8")
    return mark_safe(html)
