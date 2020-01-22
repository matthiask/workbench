from django.contrib import admin

from workbench.reporting import models


@admin.register(models.MonthlyAccrual)
class MonthlyAccrualModelAdmin(admin.ModelAdmin):
    list_display = ["cutoff_date", "accruals"]


@admin.register(models.Accrual)
class AccrualAdmin(admin.ModelAdmin):
    list_display = ["project", "cutoff_date", "accrual", "justification"]
