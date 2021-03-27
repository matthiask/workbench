from admin_ordering.admin import OrderableAdmin

from workbench.services.models import ServiceType
from workbench.tools import admin


@admin.register(ServiceType)
class ServiceTypeAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["title", "hourly_rate", "position", "color"]
    list_editable = ["position", "color"]
    ordering_field = "position"
