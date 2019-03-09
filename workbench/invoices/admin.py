from django.contrib import admin

from . import models


class EffortInline(admin.TabularInline):
    model = models.Effort
    extra = 0


class CostInline(admin.TabularInline):
    model = models.Cost
    extra = 0


@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "project_service",
        "title",
        "description",
        "position",
        "effort_hours",
        "cost",
    )
    inlines = [EffortInline, CostInline]
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
    raw_id_fields = ["customer", "contact"]
