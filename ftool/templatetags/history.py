import re

from django import template

from tools.history import changes


register = template.Library()


@register.inclusion_tag('history.html')
def history(instance, fields):
    return {
        'instance': instance,
        'changes': changes(instance, re.split(r'[\s,]+', fields)),
    }
