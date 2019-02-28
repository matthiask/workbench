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
        if instance.action == "U":
            instance.changed_fields.pop("fts_document", None)
            return json.dumps(instance.changed_fields)
        return json.dumps(instance.row_data)


admin.site.register(LoggedAction, LoggedActionAdmin)
