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
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="16" viewBox="0 0 14 16"><path fill-rule="evenodd" d="M5 12H4c-.27-.02-.48-.11-.69-.31-.21-.2-.3-.42-.31-.69V4.72A1.993 1.993 0 0 0 2 1a1.993 1.993 0 0 0-1 3.72V11c.03.78.34 1.47.94 2.06.6.59 1.28.91 2.06.94h1v2l3-3-3-3v2zM2 1.8c.66 0 1.2.55 1.2 1.2 0 .65-.55 1.2-1.2 1.2C1.35 4.2.8 3.65.8 3c0-.65.55-1.2 1.2-1.2zm11 9.48V5c-.03-.78-.34-1.47-.94-2.06-.6-.59-1.28-.91-2.06-.94H9V0L6 3l3 3V4h1c.27.02.48.11.69.31.21.2.3.42.31.69v6.28A1.993 1.993 0 0 0 12 15a1.993 1.993 0 0 0 1-3.72zm-1 2.92c-.66 0-1.2-.55-1.2-1.2 0-.65.55-1.2 1.2-1.2.65 0 1.2.55 1.2 1.2 0 .65-.55 1.2-1.2 1.2z"/></svg>
        </a>
        """,  # noqa
        reverse("history", args=(instance._meta.label_lower, instance.pk)),
        _("History"),
    )
