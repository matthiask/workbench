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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        note = _(
            "When public or company holidays are configured for this year,"
            " the corresponding month values must be increased by the number"
            " of holiday days (the import_holidays management command does"
            " this automatically)."
        )
        for field in models.Year.MONTHS:
            if field in form.base_fields:
                form.base_fields[field].help_text = note
                break
        return form


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


@admin.register(models.Holiday)
class HolidayAdmin(admin.ReadWriteModelAdmin):
    date_hierarchy = "date"
    list_display = ["date", "name", "working_time_model", "kind", "fraction"]
    list_filter = ["working_time_model", "kind"]
    radio_fields = {"kind": admin.HORIZONTAL}
