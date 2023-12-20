from admin_ordering.admin import OrderableAdmin
from django.utils.translation import gettext_lazy as _

from workbench.awt import models
from workbench.tools import admin


@admin.register(models.WorkingTimeModel)
class WorkingTimeModelAdmin(OrderableAdmin, admin.ReadWriteModelAdmin):
    list_display = ["name", "position"]
    list_editable = ["position"]
    ordering_field = "position"


@admin.register(models.Year)
class YearAdmin(admin.ReadWriteModelAdmin):
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
class EmploymentAdmin(admin.ReadWriteModelAdmin):
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
    radio_fields = {"reason": admin.HORIZONTAL}
    readonly_fields = ["is_vacation"]


@admin.register(models.VacationDaysOverride)
class VacationDaysOverrideAdmin(admin.ReadWriteModelAdmin):
    list_display = ["year", "user", "days", "notes"]
    list_filter = ["year", "user"]
    ordering = ["-year", "user"]
