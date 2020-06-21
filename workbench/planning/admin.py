from workbench.tools import admin

from . import models


@admin.register(models.PlanningTeamMembership)
class PlanningTeamMembershipAdmin(admin.ModelAdmin):
    list_display = ["project", "user"]


@admin.register(models.PlanningRequest)
class PlanningRequestAdmin(admin.ModelAdmin):
    raw_id_fields = ["project", "offer", "receivers", "created_by"]


@admin.register(models.PlannedWork)
class PlannedWorkAdmin(admin.ModelAdmin):
    raw_id_fields = ["project", "offer", "request", "user"]
