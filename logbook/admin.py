from django.contrib import admin

from logbook import models


class LoggedHoursAdmin(admin.ModelAdmin):
    list_display = (
        'task', 'created_at', 'created_by', 'rendered_by', 'hours',
        'description',
    )
    raw_id_fields = ('task', 'invoice')


admin.site.register(models.LoggedHours, LoggedHoursAdmin)
