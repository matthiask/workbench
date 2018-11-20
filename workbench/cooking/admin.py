from django.contrib import admin

from . import models


@admin.register(models.Day)
class DayAdmin(admin.ModelAdmin):
    date_hierarchy = "day"
    list_display = ["day", "handled_by"]
