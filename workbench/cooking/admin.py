from django.contrib import admin

from . import models


@admin.register(models.Day)
class DayAdmin(admin.ModelAdmin):
    date_hierarchy = "day"
    list_display = ["day", "handled_by"]


@admin.register(models.Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ["user", "year", "percentage"]
    list_editable = ["year", "percentage"]
    list_filter = ["year", "user"]
