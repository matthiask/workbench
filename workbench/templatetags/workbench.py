import math
from collections import OrderedDict
from datetime import date
from itertools import groupby
from urllib.parse import urlencode

from django import template
from django.db import models
from django.template.defaultfilters import linebreaksbr
from django.urls import reverse
from django.utils.html import format_html, format_html_join, mark_safe
from django.utils.translation import gettext as _

from workbench.tools.formats import currency, days, hours, local_date_format
from workbench.tools.models import Z


register = template.Library()


register.filter(currency)
register.filter(days)
register.filter(hours)
register.filter(local_date_format)


@register.simple_tag
def link_or_none(object, pretty=None, none=mark_safe("&ndash;"), with_badge=False):
    if not object:
        return none
    elif hasattr(object, "get_absolute_url"):
        return format_html(
            '<a href="{}">{}{}</a>',
            object.get_absolute_url(),
            h(pretty or object),
            format_html(" {}", object.status_badge)
            if with_badge and hasattr(object, "status_badge")
            else "",
        )
    return pretty or object


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
            if isinstance(value, date):
                value = local_date_format(value)
            elif isinstance(value, bool):
                value = _("yes") if value else _("no")

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


@register.simple_tag
def bar(value, one):
    if not one:
        return ""

    percentage = int(100 * value / one)

    bars = [("bg-success", min(75, max(0, percentage)))]

    if percentage >= 75:
        bars.append(("bg-caveat", min(25, percentage - 75)))
    if percentage > 100:
        bars.append(("bg-danger", percentage - 100))
        bars = [(cls, round(part * 100 / percentage, 2)) for cls, part in bars]

    return format_html(
        '<div class="progress progress-line" title="{percentage}%">{bars}</div>',
        percentage=percentage,
        bars=format_html_join(
            "",
            '<div class="progress-bar {}" role="progressbar" style="width:{}%"></div>',
            bars,
        ),
    )


@register.simple_tag
def pie(value, one, size=20):
    if not one:
        angle = 0
    else:
        angle = 2 * math.pi * min(0.999, float(value / one))

    hsize = size // 2

    return format_html(
        """\
<svg width="{size}" height="{size}" class="pie" style="display: inline-block; transform: scaleX(-1)">
  <circle r="{hsize}" cx="{hsize}" cy="{hsize}" class="pie-circle" />
  <path d="M {hsize} 0 A {hsize} {hsize} 0 {large_arc} 1 {x} {y} L {hsize} {hsize} z" class="pie-arc" />
</svg>""",  # noqa
        large_arc=1 if angle > math.pi else 0,
        x=hsize + math.sin(angle) * hsize,
        y=hsize - math.cos(angle) * hsize,
        size=size,
        hsize=hsize,
    )


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    query = urlencode(
        sorted(
            (key, value)
            for key, value in dict(context["request"].GET.items(), **kwargs).items()
            if value
        )
    )
    return "?%s" % query if query else ""


@register.simple_tag
def history_link(instance):
    if not instance.pk:
        return ""

    return format_html(
        """
        <a href="{}"
            class="tiny-icons"
            data-toggle="ajaxmodal"
            title="{}">
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="16" viewBox="0 0 14 16"><path fill-rule="evenodd" d="M13 3H7c-.55 0-1 .45-1 1v8c0 .55.45 1 1 1h6c.55 0 1-.45 1-1V4c0-.55-.45-1-1-1zm-1 8H8V5h4v6zM4 4h1v1H4v6h1v1H4c-.55 0-1-.45-1-1V5c0-.55.45-1 1-1zM1 5h1v1H1v4h1v1H1c-.55 0-1-.45-1-1V6c0-.55.45-1 1-1z"/></svg>
        </a>
        """,  # noqa
        reverse("history", args=(instance._meta.db_table, "id", instance.pk)),
        _("History"),
    )
