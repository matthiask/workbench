from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from . import models


def content_object_link(instance):
    model = instance.content_type.model_class()
    viewname = "%s_%s_detail" % (model._meta.app_label, model._meta.model_name)
    try:
        url = reverse(viewname, kwargs={"pk": instance.object_id})
    except Exception:
        return model._meta.verbose_name
    else:
        return format_html('<a href="{}">{}</a>', url, model._meta.verbose_name)


content_object_link.short_description = _("content object")


@admin.register(models.Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["title", content_object_link, "created_by", "created_at"]
    list_select_related = ["content_type", "created_by"]
    search_fields = ["title", "description"]
