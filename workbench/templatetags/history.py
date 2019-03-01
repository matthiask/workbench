import re

from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext as _

from workbench.tools.history import changes


register = template.Library()


@register.inclusion_tag("history.html")
def history(instance, fields=None):
    if not fields:
        fields = [
            f.name
            for f in instance._meta.get_fields()
            if hasattr(f, "attname") and not f.primary_key
        ]
    else:
        fields = re.split(r"[\s,]+", fields)

    return {"instance": instance, "changes": changes(instance, fields)}


@register.simple_tag
def history_link(instance):
    return format_html(
        """
        <a href="{}"
            class="tiny-icons"
            data-toggle="ajaxmodal"
            title="{}">
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="16" viewBox="0 0 14 16"><path fill-rule="evenodd" d="M13 3H7c-.55 0-1 .45-1 1v8c0 .55.45 1 1 1h6c.55 0 1-.45 1-1V4c0-.55-.45-1-1-1zm-1 8H8V5h4v6zM4 4h1v1H4v6h1v1H4c-.55 0-1-.45-1-1V5c0-.55.45-1 1-1zM1 5h1v1H1v4h1v1H1c-.55 0-1-.45-1-1V6c0-.55.45-1 1-1z"/></svg>
        </a>
        """,  # noqa
        reverse("history", args=(instance._meta.label_lower, instance.pk)),
        _("History"),
    )
