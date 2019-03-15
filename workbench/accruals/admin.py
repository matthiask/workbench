from django.contrib import admin

from . import models


@admin.register(models.Accrual)
class AccrualAdmin(admin.ModelAdmin):
    list_display = ["invoice", "month", "accrual"]
