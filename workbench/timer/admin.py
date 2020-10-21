from workbench.timer import models
from workbench.tools import admin


@admin.register(models.Timestamp)
class TimestampAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    list_display = ["user", "created_at", "type", "notes"]
    list_filter = [("user", admin.RelatedOnlyFieldListFilter)]
    radio_fields = {"type": admin.HORIZONTAL}
    raw_id_fields = ["logged_hours", "logged_break"]
