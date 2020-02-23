from pprint import pformat

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.timer import models


@admin.register(models.TimerState)
class TimerStateAdmin(admin.ModelAdmin):
    list_display = ["user", "updated_at"]
    fields = ["user", "pretty_state", "updated_at"]
    readonly_fields = ["user", "pretty_state", "updated_at"]

    def pretty_state(self, instance):
        return format_html("<code><pre>{}</pre></code>", pformat(instance.state))

    pretty_state.short_description = _("state")


@admin.register(models.Timestamp)
class TimestampAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "type", "notes"]
