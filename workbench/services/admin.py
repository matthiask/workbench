from admin_ordering.admin import OrderableAdmin

from workbench.services.models import ServiceType
from workbench.tools import admin


@admin.register(ServiceType)
class ServiceTypeAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["title", "hourly_rate", "position"]
    list_editable = ["position"]
    ordering_field = "position"
