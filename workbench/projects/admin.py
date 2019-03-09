from django.contrib import admin

from . import models


class EffortInline(admin.TabularInline):
    model = models.Effort
    extra = 0


class CostInline(admin.TabularInline):
    model = models.Cost
    extra = 0


@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "offer",
        "title",
        "description",
        "position",
        "effort_hours",
        "cost",
    )
    inlines = [EffortInline, CostInline]
    raw_id_fields = ["project", "offer"]


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "customer", "owned_by", "type", "closed_on")
    list_filter = ["type", "closed_on"]
    raw_id_fields = ("customer", "contact", "owned_by")
