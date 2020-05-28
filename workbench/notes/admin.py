from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.tools import admin

from . import models


def content_object_url(instance):
    try:
        url = instance.get_absolute_url()
    except Exception:
        return instance.content_type.name
    else:
        return format_html('<a href="{}">{}</a>', url, instance.content_type.name)


content_object_url.short_description = _("content object")


@admin.register(models.Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["title", content_object_url, "created_by", "created_at"]
    list_select_related = ["content_type", "created_by"]
    search_fields = ["title", "description"]
