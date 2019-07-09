from django.contrib import admin

from . import models


@admin.register(models.ExpenseReport)
class ExpenseReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "created_by", "owned_by", "total")
    raw_id_fields = ("created_by", "owned_by")
