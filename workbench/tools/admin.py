from django.conf import settings
from django.contrib.admin import (  # noqa
    HORIZONTAL,
    VERTICAL,
    ModelAdmin as ReadWriteModelAdmin,
    RelatedOnlyFieldListFilter,
    StackedInline,
    TabularInline,
    register,
)


class ModelAdmin(ReadWriteModelAdmin):
    def get_actions(self, request):
        return []

    def has_add_permission(self, request, obj=None):
        return settings.WORKBENCH.READ_WRITE_ADMIN

    def has_change_permission(self, request, obj=None):
        return settings.WORKBENCH.READ_WRITE_ADMIN

    def has_delete_permission(self, request, obj=None):
        return settings.WORKBENCH.READ_WRITE_ADMIN
