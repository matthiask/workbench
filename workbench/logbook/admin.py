from workbench.tools import admin

from . import models


@admin.register(models.LoggedHours)
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


@admin.register(models.LoggedCost)
class LoggedCostAdmin(admin.ModelAdmin):
    list_display = ("service", "created_by", "rendered_on", "cost", "description")
    raw_id_fields = ("service", "invoice_service", "expense_report")


@admin.register(models.Break)
class BreakAdmin(admin.ModelAdmin):
    list_display = ["user", "starts_at", "ends_at", "description"]
    raw_id_fields = ["user"]
