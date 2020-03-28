from django.contrib import admin

from . import models


class LoggedHoursAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "created_at",
        "created_by",
        "rendered_on",
        "rendered_by",
        "hours",
        "description",
    )
    raw_id_fields = ("service", "invoice_service")


class LoggedCostAdmin(admin.ModelAdmin):
    list_display = ("service", "created_by", "rendered_on", "cost", "description")
    raw_id_fields = ("service", "invoice_service", "expense_report")


class BreakAdmin(admin.ModelAdmin):
    list_display = ["user", "day", "starts_at", "ends_at", "description"]
    raw_id_fields = ["user"]


admin.site.register(models.LoggedHours, LoggedHoursAdmin)
admin.site.register(models.LoggedCost, LoggedCostAdmin)
admin.site.register(models.Break, BreakAdmin)
