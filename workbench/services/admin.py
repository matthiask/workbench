from django.contrib import admin

from admin_ordering.admin import OrderableAdmin

from workbench.services.models import ServiceType


@admin.register(ServiceType)
class ServiceTypeAdmin(OrderableAdmin, admin.ModelAdmin):
    list_display = ["title", "billing_per_hour", "position"]
    list_editable = ["position"]
    ordering_field = "position"
