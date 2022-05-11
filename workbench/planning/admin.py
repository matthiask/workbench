from workbench.planning import models
from workbench.tools import admin


@admin.register(models.PublicHoliday)
class PublicHolidayAdmin(admin.ReadWriteModelAdmin):
    list_display = ["date", "name", "fraction"]


@admin.register(models.Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ["project", "date", "title"]
    raw_id_fields = ["project"]


@admin.register(models.PlannedWork)
class PlannedWorkAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "planned_hours", "weeks"]
    raw_id_fields = ["project", "offer", "user"]


@admin.register(models.ExternalWork)
class ExternalWorkAdmin(admin.ModelAdmin):
    list_display = ["project", "provided_by", "weeks"]
    raw_id_fields = ["project"]
