from django.contrib import admin

from . import models


@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "offer",
        "title",
        "service_hours",
        "service_cost",
    )
    list_select_related = ["project__owned_by", "offer__project", "offer__owned_by"]
    raw_id_fields = ["project", "offer", "role"]
    search_fields = ["project__title", "title", "description"]


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "customer", "owned_by", "type", "closed_on")
    list_filter = ["type", "closed_on"]
    raw_id_fields = ["customer", "contact", "owned_by", "campaign"]


@admin.register(models.Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["title", "customer", "owned_by"]
    raw_id_fields = ["customer", "owned_by"]
