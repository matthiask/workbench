from workbench.credit_control import models
from workbench.tools import admin


@admin.register(models.Ledger)
class LedgerAdmin(admin.ReadWriteModelAdmin):
    radio_fields = {"parser": admin.VERTICAL}


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
    raw_id_fields = ["invoice"]
