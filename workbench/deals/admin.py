from admin_ordering.admin import OrderableAdmin

from workbench.deals import models
from workbench.tools import admin


class ValueInline(admin.TabularInline):
    model = models.Value
    extra = 0


@admin.register(models.Deal)
class DealAdmin(admin.ModelAdmin):
    inlines = [ValueInline]
    list_display = ["title", "owned_by", "value", "status", "probability", "created_at"]
    list_filter = ["status"]
    raw_id_fields = ["customer", "contact", "owned_by", "related_offers"]
    search_fields = ["title", "description"]


@admin.register(models.ValueType)
class ValueTypeAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["title", "is_archived", "position", "weekly_target"]
    list_editable = ["position", "weekly_target"]
    ordering_field = "position"


class AttributeInline(OrderableAdmin, admin.TabularInline):
    model = models.Attribute
    extra = 0
    fk_name = "group"
    ordering_field = "position"


@admin.register(models.AttributeGroup)
class AttributeGroupAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    inlines = [AttributeInline]
    list_display = ["title", "is_archived", "is_required", "position"]
    list_editable = ["position"]
    ordering_field = "position"


@admin.register(models.ClosingType)
class ClosingType(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["title", "represents_a_win", "position"]
    list_editable = ["position"]
    ordering_field = "position"
