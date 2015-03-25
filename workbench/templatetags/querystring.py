from functools import reduce
import operator

from django import template
from django.utils.http import urlencode


register = template.Library()


@register.filter
def querystring(data, exclude='page,all'):
    """
    Returns the current querystring, excluding specified GET parameters::

        {% request.GET|querystring:"page,all" %}
    """

    exclude = exclude.split(',')

    items = reduce(
        operator.add,
        (
            list((k, v) for v in values)
            for k, values
            in data.lists()
            if k not in exclude
        ),
        [])

    return urlencode(sorted(items))
