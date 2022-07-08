from workbench.invoices import models
from workbench.tools import admin


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
    raw_id_fields = (
        "customer",
        "contact",
        "project",
        "down_payment_applied_to",
        "structured_billing_address",
    )


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
    raw_id_fields = ["customer", "contact", "structured_billing_address"]


@admin.register(models.ProjectedInvoice)
class ProjectedInvoiceAdmin(admin.ReadWriteModelAdmin):
    date_hierarchy = "invoiced_on"
    list_display = ["project", "invoiced_on", "gross_margin", "description"]
    ordering = ["-invoiced_on", "project"]
    raw_id_fields = ["project"]


@admin.register(models.StructuredBillingAddress)
class StructuredBillingAddressAdmin(admin.ModelAdmin):
    list_display = ["name", "city"]
    ordering = ["name"]
