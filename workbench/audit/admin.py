import json

from django.contrib import admin

from workbench.audit.models import LoggedAction


class LoggedActionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "data", "user_name", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in LoggedAction._meta.get_fields()]

    def get_actions(self, request):
        return []

    def data(self, instance):
        return json.dumps(
            instance.changed_fields if instance.action == "U" else instance.row_data
        )


admin.site.register(LoggedAction, LoggedActionAdmin)
