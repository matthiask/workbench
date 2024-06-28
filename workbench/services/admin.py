from admin_ordering.admin import OrderableAdmin

from workbench.services.models import ServiceType
from workbench.tools import admin


@admin.register(ServiceType)
class ServiceTypeAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["__str__", "title", "hourly_rate", "color", "position"]
    list_editable = ["title", "hourly_rate", "color", "position"]
    ordering_field = "position"
