from workbench.tools import admin

from . import models


@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "project_service",
        "title",
        "description",
        "position",
        "service_hours",
        "service_cost",
    )
    raw_id_fields = ["invoice", "project_service"]


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    date_hierarchy = "invoiced_on"
    list_display = (
        "title",
        "customer",
        "invoiced_on",
        "owned_by",
        "type",
        "status",
        "total_excl_tax",
    )
    list_filter = ("type", "status")
    radio_fields = {"status": admin.HORIZONTAL, "type": admin.HORIZONTAL}
    raw_id_fields = ("customer", "contact", "project", "down_payment_applied_to")


@admin.register(models.RecurringInvoice)
class RecurringInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "customer",
        "owned_by",
        "starts_on",
        "ends_on",
        "periodicity",
        "next_period_starts_on",
        "total_excl_tax",
    ]
    list_filter = ["periodicity"]
    radio_fields = {"periodicity": admin.HORIZONTAL}
    raw_id_fields = ["customer", "contact"]
