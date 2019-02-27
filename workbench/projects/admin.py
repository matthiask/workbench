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


class ServiceInline(admin.TabularInline):
    model = models.Service
    extra = 0


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    inlines = [ServiceInline]
    list_display = ("title", "customer", "owned_by", "status")
    list_filter = ("status",)
    raw_id_fields = ("customer", "contact", "owned_by")
