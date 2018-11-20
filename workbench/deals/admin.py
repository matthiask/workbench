from django.contrib import admin

from workbench.deals.models import Deal, Stage


class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "owned_by", "estimated_value", "status", "created_at")
    list_display_links = ("title",)
    list_filter = ("status",)
    raw_id_fields = ("owned_by",)
    search_fields = ("title", "description")


admin.site.register(Deal, DealAdmin)
admin.site.register(
    Stage, list_display=("title", "position"), list_editable=("position",)
)
