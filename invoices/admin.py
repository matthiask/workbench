from django.contrib import admin

from invoices import models


class InvoiceAdmin(admin.ModelAdmin):
    raw_id_fields = (
        'customer', 'contact', 'project', 'stories',
        'down_payment_applied_to')


admin.site.register(models.Invoice, InvoiceAdmin)
