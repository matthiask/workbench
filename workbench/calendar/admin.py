from django.contrib import admin

from admin_ordering.admin import OrderableAdmin

from . import models


@admin.register(models.App)
class AppAdmin(OrderableAdmin, admin.ModelAdmin):
    filter_horizontal = ["users"]
    list_display = ["title", "ordering"]
    list_editable = ["ordering"]
    ordering_field = "ordering"
    prepopulated_fields = {"slug": ["title"]}


@admin.register(models.Day)
class DayAdmin(admin.ModelAdmin):
    date_hierarchy = "day"
    list_display = ["app", "day", "handled_by"]
    list_filter = ["app"]


@admin.register(models.Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ["app", "user", "year", "percentage"]
    list_editable = ["year", "percentage"]
    list_filter = ["app", "year", "user"]


@admin.register(models.DayOfWeekDefault)
class DayOfWeekDefaultAdmin(admin.ModelAdmin):
    list_display = ["app", "user", "day_of_week"]
    list_filter = ["app"]
