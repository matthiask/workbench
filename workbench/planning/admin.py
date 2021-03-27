from workbench.tools import admin

from . import models


@admin.register(models.PlannedWork)
class PlannedWorkAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "planned_hours", "weeks"]
    raw_id_fields = ["project", "offer", "user"]
