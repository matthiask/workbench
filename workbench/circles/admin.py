from workbench.tools import admin

from . import models


@admin.register(models.Circle)
class CircleAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Role)
class RoleAdmin(admin.ReadWriteModelAdmin):
    list_display = ["name", "circle", "for_circle", "is_removed", "work_category"]
    list_editable = ["work_category"]
    list_filter = ["work_category", "circle", "is_removed"]
    readonly_fields = ["circle", "name", "for_circle", "is_removed"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
