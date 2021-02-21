from workbench.tools import admin

from . import models


@admin.register(models.ReceivedRequest)
class ReceivedRequestAdmin(admin.ModelAdmin):
    list_display = ["request", "user", "created_at", "declined_at", "reason"]
    raw_id_fields = ["request", "user"]


@admin.register(models.PlanningRequest)
class PlanningRequestAdmin(admin.ModelAdmin):
    filter_horizontal = ["receivers"]
    raw_id_fields = ["project", "offer", "created_by"]


@admin.register(models.PlannedWork)
class PlannedWorkAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "planned_hours", "weeks"]
    raw_id_fields = ["project", "offer", "request", "user"]
