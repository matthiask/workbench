import json

from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction, audit_user_id
from workbench.tools import admin


class UserFilter(admin.SimpleListFilter):
    title = _("user")
    parameter_name = "user"

    def lookups(self, request, model_admin):
        users = {user.id: user for user in User.objects.all()}

        def choice(user_name):
            if user := users.get(audit_user_id(user_name)):
                return (f"user-{user.id}-{user.get_short_name()}", str(user))
            return (user_name, user_name)

        return sorted(
            dict(
                choice(user_name)
                for user_name in LoggedAction.objects.values_list(
                    "user_name", flat=True
                )
                .order_by()
                .distinct()
            ).items(),
            key=lambda row: (2, row[1]) if row[0].startswith("user-") else (1, row[0]),
        )

    def queryset(self, request, queryset):
        if value := self.value():
            if user_id := audit_user_id(value):
                queryset = queryset.filter(user_name__startswith=f"user-{user_id}-")
            else:
                queryset = queryset.filter(user_name=value)
        return queryset


@admin.register(LoggedAction)
class LoggedActionAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user_name", "table_name", "id", "action", "data"]
    list_filter = ["action", "table_name", UserFilter]
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
