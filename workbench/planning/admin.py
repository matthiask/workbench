from workbench.tools import admin

from . import models


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
