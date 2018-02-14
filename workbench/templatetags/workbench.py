from collections import OrderedDict, defaultdict
from datetime import date, datetime
from decimal import Decimal
import itertools

from django import template
from django.db import models
from django.db.models import Count, Sum
from django.template.defaultfilters import linebreaksbr
from django.utils import timezone
from django.utils.html import format_html, mark_safe
from django.utils.translation import ugettext as _

from logbook.models import LoggedHours
from offers.models import Service
from projects.models import Comment
from tools.formats import local_date_format


register = template.Library()


@register.simple_tag
def link_or_none(object, pretty=None):
    if not object:
        return mark_safe('&ndash;')
    elif hasattr(object, 'get_absolute_url'):
        return format_html(
            '<a href="{}">{}</a>',
            object.get_absolute_url(),
            h(pretty or object),
        )
    return pretty or object


@register.filter
def currency(value):
    return '{:,.2f}'.format(value).replace(',', "’")


@register.filter
def field_value_pairs(object, fields=''):
    pairs = OrderedDict()
    for field in object._meta.get_fields():
        if field.one_to_many or field.many_to_many or field.primary_key:
            continue

        if field.choices:
            pairs[field.name] = (
                field.verbose_name, object._get_FIELD_display(field))

        elif isinstance(field, models.TextField):
            pairs[field.name] = (
                field.verbose_name,
                linebreaksbr(getattr(object, field.name)))

        else:
            value = getattr(object, field.name)
            if isinstance(value, datetime):
                value = local_date_format(value, 'd.m.Y H:i')
            elif isinstance(value, date):
                value = local_date_format(value, 'd.m.Y')

            pairs[field.name] = (field.verbose_name, value)

    if fields:
        for f in fields.split(','):
            yield pairs[f.strip()]
    else:
        yield from pairs.values()


@register.filter
def h(object):
    if hasattr(object, '__html__'):
        return object.__html__()
    return object


@register.filter
def percentage_to_css(value):
    if value < 80:
        return 'info'
    elif value < 100:
        return 'warning'
    return 'danger'


@register.filter
def select_related(queryset, rel):
    return queryset.select_related(*rel.split(','))


@register.filter
def prefetch_related(queryset, rel):
    return queryset.prefetch_related(*rel.split(','))


@register.filter
def group_hours_by_day(iterable):
    for day, instances in itertools.groupby(
            iterable,
            lambda logged: logged.rendered_on,
    ):
        instances = list(instances)
        yield (
            day,
            sum((item.hours for item in instances), Decimal()),
            instances,
        )


@register.filter
def timesince_short(dttm):
    delta = int((timezone.now() - dttm).total_seconds())
    if delta > 86400 * 180:
        return _('%s months ago') % int(delta // (86400 * 365 / 12))
    if delta > 86400 * 14:
        return _('%s weeks ago') % (delta // (86400 * 7))
    if delta > 86400 * 2:
        return _('%s days ago') % (delta // 86400)
    if delta > 7200:
        return _('%s hours ago') % (delta // 3600)
    if delta > 120:
        return _('%s minutes ago') % (delta // 60)
    return _('%s seconds ago') % delta


@register.filter
def tasks_info(tasks, project):
    tasks = list(tasks)

    comment_counts = {
        row['task']: row['count']
        for row in Comment.objects.filter(
            task__project=project,
        ).order_by().values('task').annotate(
            count=Count('id'),
        )
    }

    hours_per_task = {
        row['task']: row['hours__sum']
        for row in LoggedHours.objects.order_by().filter(
            task__project=project,
        ).values('task').annotate(
            Sum('hours'),
        )
    }
    hours_per_service = {
        row['task__service']: row['hours__sum']
        for row in LoggedHours.objects.order_by().filter(
            task__project=project,
        ).values('task__service').annotate(
            Sum('hours'),
        )
    }
    hours_per_task = {
        row['task']: row['hours__sum']
        for row in LoggedHours.objects.order_by().filter(
            task__project=project,
        ).values('task').annotate(
            Sum('hours'),
        )
    }

    tasks_per_service = defaultdict(list)
    for task in tasks:
        task.comment_count = comment_counts.get(task.id, 0)
        task.logged_hours = hours_per_task.get(task.id, 0)
        tasks_per_service[task.service].append(task)

    if tasks_per_service[None] or None in hours_per_service:
        yield (
            None,
            hours_per_service.get(None, Decimal()),
            tasks_per_service[None],
        )

    for service in Service.objects.filter(
            offer__project=project).select_related('offer'):
        yield (
            service,
            hours_per_service.get(service.id, Decimal()),
            tasks_per_service[service],
        )
