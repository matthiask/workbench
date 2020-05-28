import json

from workbench.audit.models import LoggedAction
from workbench.tools import admin


@admin.register(LoggedAction)
class LoggedActionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "data", "user_name", "created_at")
    list_filter = ["action", "table_name"]
    ordering = ("-created_at",)

    def data(self, instance):
        return json.dumps(
            instance.changed_fields if instance.action == "U" else instance.row_data
        )
