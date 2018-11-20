import re

from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext as _

from tools.history import changes


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
          <i class="glyphicon glyphicon-time"></i>
        </a>
        """,
        reverse("history", args=(instance._meta.label_lower, instance.pk)),
        _("History"),
    )
