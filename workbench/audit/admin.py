import json

from workbench.audit.models import LoggedAction
from workbench.tools import admin


@admin.register(LoggedAction)
class LoggedActionAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user_name", "table_name", "id", "action", "data"]
    list_filter = ["action", "table_name"]
    ordering = ("-created_at",)

    def id(self, instance):
        try:
            return instance.row_data["id"]
        except Exception:
            return None

    def data(self, instance):
        return json.dumps(
            instance.changed_fields if instance.action == "U" else instance.row_data
        )
