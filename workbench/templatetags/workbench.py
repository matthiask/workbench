from collections import OrderedDict
from datetime import date, datetime
from itertools import groupby

from django import template
from django.db import models
from django.template.defaultfilters import linebreaksbr
from django.utils import timezone
from django.utils.html import format_html, format_html_join, mark_safe
from django.utils.translation import ugettext as _

from workbench.tools.formats import local_date_format
from workbench.tools.models import Z


register = template.Library()


@register.simple_tag
def link_or_none(object, pretty=None):
    if not object:
        return mark_safe("&ndash;")
    elif hasattr(object, "get_absolute_url"):
        return format_html(
            '<a href="{}">{}</a>', object.get_absolute_url(), h(pretty or object)
        )
    return pretty or object


@register.filter
def currency(value):
    return "{:,.2f}".format(value).replace(",", "’")


@register.filter
def field_value_pairs(object, fields=""):
    pairs = OrderedDict()
    for field in object._meta.get_fields():
        if field.one_to_many or field.many_to_many or field.primary_key:
            continue

        if field.choices:
            pairs[field.name] = (field.verbose_name, object._get_FIELD_display(field))

        elif isinstance(field, models.TextField):
            pairs[field.name] = (
                field.verbose_name,
                linebreaksbr(getattr(object, field.name)),
            )

        else:
            value = getattr(object, field.name)
            if isinstance(value, datetime):
                value = local_date_format(value, "d.m.Y H:i")
            elif isinstance(value, date):
                value = local_date_format(value, "d.m.Y")

            pairs[field.name] = (field.verbose_name, value)

    if fields:
        for f in fields.split(","):
            yield pairs[f.strip()]
    else:
        yield from pairs.values()


@register.filter
def h(object):
    if hasattr(object, "__html__"):
        return object.__html__()
    return object


@register.filter
def group_hours_by_day(iterable):
    for day, instances in groupby(iterable, lambda logged: logged.rendered_on):
        instances = list(instances)
        yield (day, sum((item.hours for item in instances), Z), instances)


@register.filter
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


@register.simple_tag
def bar(value, one):
    if not one:
        return ""

    percentage = int(100 * value / one)

    bars = []

    if percentage < 75:
        bars.append(("bg-info", percentage))
    elif percentage <= 100:
        bars.append(("bg-warning", percentage))
    else:
        bars.extend(
            [
                ("bg-warning", int(10000 / percentage)),
                ("bg-danger", 100 - int(10000 / percentage)),
            ]
        )

    return format_html(
        '<div class="progress progress-line">{bars}</div>',
        bars=format_html_join(
            "",
            '<div class="progress-bar {}" role="progressbar" style="width:{}%"></div>',
            bars,
        ),
    )
