from django.contrib import admin

from . import models


class LoggedHoursAdmin(admin.ModelAdmin):
    list_display = (
        "task",
        "created_at",
        "created_by",
        "rendered_on",
        "rendered_by",
        "hours",
        "description",
    )
    raw_id_fields = ("task", "invoice")


class LoggedCostAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "service",
        "created_by",
        "rendered_on",
        "cost",
        "description",
    )
    raw_id_fields = ("project", "service", "invoice")


admin.site.register(models.LoggedHours, LoggedHoursAdmin)
admin.site.register(models.LoggedCost, LoggedCostAdmin)
