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
            pretty or object,
        )
    return pretty or object


@register.filter
def currency(value):
    return '{:,.2f}'.format(value).replace(',', "’")
