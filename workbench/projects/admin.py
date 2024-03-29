from admin_ordering.admin import OrderableAdmin

from workbench.projects import models
from workbench.tools import admin


class InternalTypeUserInline(admin.TabularInline):
    model = models.InternalTypeUser
    extra = 0
    ordering = ["user"]


@admin.register(models.InternalType)
class InternalTypeAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    inlines = [InternalTypeUserInline]
    list_display = ["name", "description", "percentage", "ordering"]
    list_editable = ["ordering"]


@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "project",
        "offer",
        "service_hours",
        "service_cost",
    )
    list_select_related = ["project__owned_by", "offer__project", "offer__owned_by"]
    ordering = ["-pk"]
    raw_id_fields = ["project", "offer"]
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
