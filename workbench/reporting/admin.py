from django.contrib import admin

from workbench.reporting.models import Accruals


@admin.register(Accruals)
class AccrualsModelAdmin(admin.ModelAdmin):
    list_display = ["cutoff_date", "accruals"]
