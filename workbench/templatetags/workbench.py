import datetime as dt
import math
from itertools import groupby
from urllib.parse import urlencode

from django import template
from django.db import connections, models
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
    if object == 0:
        return object
    elif not object:
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
def field_value_pairs(object):
    for field in object._meta.get_fields():
        if field.one_to_many or field.many_to_many or field.primary_key:
            continue

        if field.choices:
            yield (field.verbose_name, object._get_FIELD_display(field))

        elif isinstance(field, models.TextField):
            yield (
                field.verbose_name,
                linebreaksbr(getattr(object, field.name)),
            )

        else:
            value = getattr(object, field.name)
            if isinstance(value, dt.date):
                value = local_date_format(value)
            elif isinstance(value, bool):
                value = _("yes") if value else _("no")

            yield (field.verbose_name, value)


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
def pie(value, one, size=20, type="bad"):
    if not one:
        angle = 0
    else:
        angle = 2 * math.pi * min(0.999, float(value / one))

    hsize = size // 2

    return format_html(
        """\
<svg width="{size}" height="{size}" class="pie {type}" style="display: inline-block">
  <circle r="{hsize}" cx="{hsize}" cy="{hsize}" class="pie-circle" />
  <path d="M {hsize} 0 A {hsize} {hsize} 0 {large_arc} 1 {x} {y} L {hsize} {hsize} z" class="pie-arc" />
</svg>""",  # noqa
        large_arc=1 if angle > math.pi else 0,
        x=hsize + math.sin(angle) * hsize,
        y=hsize - math.cos(angle) * hsize,
        size=size,
        hsize=hsize,
        type=type,
    )


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    query = urlencode(
        sorted(
            (key, value)
            for key, value in dict(context["request"].GET.items(), **kwargs).items()
            if key not in {"_error"} and value
        )
    )
    return "?%s" % query if query else ""


@register.simple_tag(takes_context=True)
def page_links(context, page_obj):
    for page in page_obj.paginator.page_range:
        if abs(page - page_obj.number) < 7:
            yield page, querystring(context, page=page)


@register.simple_tag
def history_link(instance):
    return (
        format_html(
            """\
<a href="{}"
    class="tiny-icons"
    data-toggle="ajaxmodal"
    title="{}">
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="16" viewBox="0 0 14 16"><path fill-rule="evenodd" d="M13 3H7c-.55 0-1 .45-1 1v8c0 .55.45 1 1 1h6c.55 0 1-.45 1-1V4c0-.55-.45-1-1-1zm-1 8H8V5h4v6zM4 4h1v1H4v6h1v1H4c-.55 0-1-.45-1-1V5c0-.55.45-1 1-1zM1 5h1v1H1v4h1v1H1c-.55 0-1-.45-1-1V6c0-.55.45-1 1-1z"/></svg>
</a>""",  # noqa
            reverse("history", args=(instance._meta.db_table, "id", instance.pk)),
            _("History"),
        )
        if instance.pk
        else ""
    )


@register.simple_tag
def project_statistics_row(project_logged_hours, service_logged_hours):
    service = dict(service_logged_hours)
    return [(user, service.get(user)) for user, _ in project_logged_hours]


@register.simple_tag
def percentage(value, one):
    return (
        format_html(
            '<span class="font-weight-normal text-black-30">{}%</span>',
            round(100 * value / one),
        )
        if one
        else ""
    )


@register.simple_tag
def birthdays():
    with connections["default"].cursor() as cursor:
        cursor.execute(
            """
SELECT id, given_name, family_name, date_of_birth FROM (
    SELECT
        id,
        given_name,
        family_name,
        date_of_birth,
        (current_date - date_of_birth) % 365.24 AS diff
    FROM contacts_person
    WHERE date_of_birth is not null
) AS subquery
WHERE diff < 7 or diff > 350
ORDER BY (diff + 180) % 365 DESC
            """
        )
        return [
            {
                "id": row[0],
                "given_name": row[1],
                "family_name": row[2],
                "date_of_birth": row[3],
            }
            for row in cursor
        ]


@register.filter
def has(user, feature):
    return user.features[feature]
