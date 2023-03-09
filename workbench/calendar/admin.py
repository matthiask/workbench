from django.contrib import admin

from admin_ordering.admin import OrderableAdmin

from . import models


@admin.register(models.App)
class AppAdmin(OrderableAdmin, admin.ModelAdmin):
    filter_horizontal = ["users"]
    list_display = ["title", "ordering", "is_paused"]
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
    ordering = ["app", "user", "year"]


@admin.register(models.DayOfWeekDefault)
class DayOfWeekDefaultAdmin(admin.ModelAdmin):
    list_display = ["app", "user", "day_of_week"]
    list_filter = ["app"]
    ordering = ["app", "day_of_week"]

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(models.PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    date_hierarchy = "day"
    list_display = ["name", "day"]
    ordering = ["day"]


@admin.register(models.CompanyHoliday)
class CompanyHolidayAdmin(admin.ModelAdmin):
    date_hierarchy = "date_from"
    list_display = ["date_from", "date_until"]
    ordering = ["date_from"]
