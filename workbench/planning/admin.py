from workbench.tools import admin

from . import models


@admin.register(models.PlanningRequest)
class PlanningRequestAdmin(admin.ReadWriteModelAdmin):
    filter_horizontal = ["receivers"]
    raw_id_fields = ["project", "offer", "created_by"]


@admin.register(models.PlannedWork)
class PlannedWorkAdmin(admin.ReadWriteModelAdmin):
    list_display = ["project", "user", "planned_hours", "weeks"]
    raw_id_fields = ["project", "offer", "request", "user"]
