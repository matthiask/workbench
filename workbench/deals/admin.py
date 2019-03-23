from django.contrib import admin

from admin_ordering.admin import OrderableAdmin
from workbench.deals.models import Deal, Stage


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "owned_by", "estimated_value", "status", "created_at")
    list_display_links = ("title",)
    list_filter = ("status",)
    raw_id_fields = ["customer", "contact", "owned_by"]
    search_fields = ("title", "description")


@admin.register(Stage)
class StageAdmin(OrderableAdmin, admin.ModelAdmin):
    list_display = ["title", "position"]
    list_editable = ["position"]
    ordering_field = "position"
