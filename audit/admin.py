from django.contrib import admin

from audit.models import LoggedAction


class LoggedActionAdmin(admin.ModelAdmin):
    date_hierarchy = 'action_tstamp_stm'
    list_display = (
        '__str__',
        'action_tstamp_stm',
        'client_query',
    )
    ordering = ('-action_tstamp_stm',)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in LoggedAction._meta.get_fields()]

    def get_actions(self, request):
        return []


admin.site.register(LoggedAction, LoggedActionAdmin)
