import re

from django import template

from tools.history import changes


register = template.Library()


@register.inclusion_tag('history.html')
def history(instance, fields=None):
    if fields is None:
        fields = [f.name for f in instance._meta.get_fields()]
    else:
        fields = re.split(r'[\s,]+', fields)

    return {
        'instance': instance,
        'changes': changes(instance, fields),
    }
