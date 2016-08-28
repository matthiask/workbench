from collections import OrderedDict

from django import template
from django.utils.html import format_html, mark_safe


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
        else:
            pairs[field.name] = (
                field.verbose_name, getattr(object, field.name))

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
