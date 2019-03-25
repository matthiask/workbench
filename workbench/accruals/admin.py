from django.contrib import admin

from . import models


@admin.register(models.CutoffDate)
class CutoffDateAdmin(admin.ModelAdmin):
    list_display = ["day"]


@admin.register(models.Accrual)
class AccrualAdmin(admin.ModelAdmin):
    list_display = ["invoice", "cutoff_date", "work_progress"]
