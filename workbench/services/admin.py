from django.contrib import admin

from admin_ordering.admin import OrderableAdmin
from workbench.services.models import ServiceType


@admin.register(ServiceType)
class ServiceTypeAdmin(OrderableAdmin, admin.ModelAdmin):
    list_display = ["title", "hourly_rate", "position"]
    list_editable = ["position"]
    ordering_field = "position"
