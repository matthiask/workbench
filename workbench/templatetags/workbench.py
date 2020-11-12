import datetime as dt
import math
from itertools import groupby

from django import template
from django.db import models
from django.db.models import Sum
from django.template.defaultfilters import linebreaksbr
from django.urls import reverse
from django.utils.html import format_html, format_html_join, mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from workbench.logbook.models import LoggedHours
from workbench.notes.forms import NoteForm
from workbench.notes.models import Note
from workbench.projects.models import Service
from workbench.tools.formats import Z1, Z2, currency, days, hours, local_date_format
from workbench.tools.forms import querystring as _qs
from workbench.tools.history import EVERYTHING


register = template.Library()


register.filter(currency)
register.filter(days)
register.filter(hours)


@register.filter(name="local_date_format")
def local_date_format_filter(dttm, fmt=None):
    return local_date_format(dttm, fmt=fmt)


@register.simple_tag
def link_or_none(object, pretty=None, none=mark_safe("&ndash;"), with_badge=False):
    if object == 0:
        return object
    elif not object:
        return none
    elif hasattr(object, "html_link"):
        return object.html_link()
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
def field_value_pairs(object, fields=None):
    fields = (
        fields.split(",")
        if fields
        else getattr(object, "field_value_pairs", EVERYTHING)
    )
    for field in object._meta.get_fields():
        if (
            field.one_to_many
            or field.one_to_one
            or field.many_to_many
            or field.primary_key
            or field.name in {"_fts"}
            or field.name not in fields
        ):
            continue

        if field.choices:
            yield (capfirst(field.verbose_name), object._get_FIELD_display(field))

        elif isinstance(field, models.TextField):
            yield (
                capfirst(field.verbose_name),
                linebreaksbr(getattr(object, field.name)),
            )

        else:
            value = getattr(object, field.name)
            if isinstance(value, dt.date):
                value = local_date_format(value)
            elif isinstance(value, bool):
                value = _("yes") if value else _("no")

            yield (capfirst(field.verbose_name), value)


@register.filter
def h(object):
    if hasattr(object, "__html__"):
        return object.__html__()
    return object


@register.filter
def group_hours_by_day(iterable):
    for day, instances in groupby(iterable, lambda logged: logged.rendered_on):
        instances = list(instances)
        yield (day, sum((item.hours for item in instances), Z1), instances)


def deal_group(deal):
    decision_expected_within = (
        (deal.decision_expected_on - dt.date.today()).days
        if deal.decision_expected_on
        else 99999999999
    )

    if deal.probability == deal.HIGH:
        if decision_expected_within <= 4 * 7:
            return (1, _("high probability, next 4 weeks"))
        elif decision_expected_within <= 12 * 7:
            return (2, _("high probability, next 12 weeks"))
        else:
            return (3, _("high probability, later"))
    elif deal.probability == deal.NORMAL:
        return (4, _("normal probability"))
    else:
        return (5, _("unknown probability"))


@register.filter
def group_deals_by_probability(iterable, should_group):
    if not should_group:
        deals = list(iterable)
        yield {
            "title": capfirst(iterable.model._meta.verbose_name_plural),
            "deals": deals,
            "sum": sum((deal.value for deal in deals), Z2),
        }
        return

    for group, deals in groupby(iterable, deal_group):
        deals = list(deals)
        yield {
            "title": group[1],
            "deals": deals,
            "sum": sum((deal.value for deal in deals), Z2),
        }


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
        size=size + 2,
        hsize=hsize,
        type=type,
    )


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    return _qs(context["request"].GET, **kwargs)


@register.simple_tag(takes_context=True)
def page_links(context, page_obj):
    return (
        (page, querystring(context, page=page))
        for page in page_obj.paginator.page_range
        if abs(page - page_obj.number) < 7
    )


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


@register.filter
def has_feature(user, feature):
    if not hasattr(user, "features"):  # e.g. AnonymousUser
        return False
    return user.features[feature]


@register.filter
def label(instance, field):
    return capfirst(instance._meta.get_field(field).verbose_name)


@register.filter
def addf(a, b):
    """Add values without converting them to integers (as |add seems to do)"""
    return a + b


@register.inclusion_tag("notes/widget.html", takes_context=True)
def notes(context, instance):
    request = context["request"]
    notes = (
        Note.objects.for_content_object(instance).select_related("created_by").reverse()
    )
    return {
        "form": NoteForm(request=request, content_object=instance),
        "notes": notes,
        "request": request,
    }


@register.filter
def analyze_projects(object_list):
    pks = [object.pk for object in object_list]
    service_hours = {
        row["project"]: row["service_hours__sum"]
        for row in Service.objects.budgeted()
        .filter(project__in=pks)
        .order_by()
        .values("project")
        .annotate(Sum("service_hours"))
    }
    logged_hours = {
        row["service__project"]: row["hours__sum"]
        for row in LoggedHours.objects.filter(service__project__in=pks)
        .order_by()
        .values("service__project")
        .annotate(Sum("hours"))
    }

    for object in object_list:
        object.analyzed = {
            "service_hours": service_hours.get(object.pk, 0),
            "logged_hours": logged_hours.get(object.pk, 0),
        }
    return object_list
