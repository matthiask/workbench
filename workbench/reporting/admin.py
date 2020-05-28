from admin_ordering.admin import OrderableAdmin

from workbench.reporting import models
from workbench.tools import admin


@admin.register(models.Accruals)
class AccrualsModelAdmin(admin.ModelAdmin):
    list_display = ["cutoff_date", "accruals"]


@admin.register(models.CostCenter)
class CostCenter(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["title", "position"]
    list_editable = ["position"]
    ordering_field = "position"
