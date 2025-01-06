from admin_ordering.admin import OrderableAdmin

from workbench.reporting import models
from workbench.tools import admin


@admin.register(models.Accruals)
class AccrualsAdmin(admin.ModelAdmin):
    list_display = ["cutoff_date", "accruals"]


@admin.register(models.CostCenter)
class CostCenterAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["title", "position"]
    list_editable = ["position"]
    ordering_field = "position"


@admin.register(models.FreezeDate)
class FreezeDateAdmin(admin.ModelAdmin):
    list_display = ["up_to", "created_at"]
    ordering = ["-up_to"]
