from django.contrib import admin

from workbench.credit_control import models


@admin.register(models.AccountStatement)
class AccountStatementAdmin(admin.ModelAdmin):
    list_display = ["created_at", "created_by", "processed_at", "statement", "title"]
    raw_id_fields = ["created_by"]


@admin.register(models.CreditEntry)
class CreditEntryAdmin(admin.ModelAdmin):
    list_display = [
        "reference_number",
        "value_date",
        "total",
        "payment_notice",
        "invoice",
        "notes",
    ]
    list_select_related = ["invoice__owned_by", "invoice__project"]
    raw_id_fields = ["account_statement", "invoice"]
