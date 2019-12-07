from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from . import models


@admin.register(models.WorkingTimeModel)
class WorkingTimeModelAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Year)
class YearAdmin(admin.ModelAdmin):
    list_display = [
        "year",
        "working_time_model",
        "working_time_per_day",
        *models.Year.MONTHS,
        "days",
    ]

    def days(self, instance):
        return sum(instance.months)

    days.short_description = _("days")


@admin.register(models.Employment)
class EmploymentAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "date_from",
        "date_until",
        "percentage",
        "vacation_weeks",
        "notes",
    ]
    list_filter = ["user", "date_from"]


@admin.register(models.Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ["user", "starts_on", "days", "description", "is_vacation"]
