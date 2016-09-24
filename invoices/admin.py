from django.contrib import admin

from invoices import models


class InvoiceAdmin(admin.ModelAdmin):
    date_hierarchy = 'invoiced_on'
    list_display = (
        'title', 'customer', 'project', 'invoiced_on', 'owned_by', 'type',
        'status', 'total')
    list_filter = ('type', 'status',)
    raw_id_fields = (
        'customer', 'contact', 'project', 'down_payment_applied_to')


admin.site.register(models.Invoice, InvoiceAdmin)
