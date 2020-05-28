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
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
