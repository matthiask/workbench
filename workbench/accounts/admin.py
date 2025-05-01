from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from workbench.accounts.features import FEATURES, LABELS, F
from workbench.accounts.models import SpecialistField, Team, User
from workbench.awt.models import Employment, VacationDaysOverride


class FeaturesWidget(forms.TextInput):
    template_name = "widgets/features.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        current = set((value or "").split(","))

        def checkbox(feature, **kwargs):
            ret = {"value": feature, **kwargs}
            value = settings.FEATURES.get(feature, F.NEVER)
            if value == F.ALWAYS:
                ret["attrs"] = "checked disabled"
            elif value == F.NEVER:
                ret["attrs"] = "disabled"
                ret["style"] = "opacity:0.5;"
            elif feature in current:
                ret["attrs"] = "checked"
            return ret

        features = ((f, settings.FEATURES.get(f, F.NEVER)) for f in FEATURES)
        ordering = {F.ALWAYS: 1, F.USER: 2, F.NEVER: 3}
        context["widget"]["features"] = [
            checkbox(feature.value, **LABELS[feature])
            for feature, value in sorted(features, key=lambda row: ordering[row[1]])
        ]
        return context

    def value_from_datadict(self, data, files, name):
        return sorted(set(data.getlist(name) or ()))

    def value_omitted_from_data(self, data, files, name):
        # HTML checkboxes don't appear in POST data if not checked, so it's
        # never known if the value is actually omitted.
        return False


class UserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = "__all__"  # noqa: DJ007
        widgets = {"_features": FeaturesWidget}


class EmploymentInline(admin.TabularInline):
    model = Employment
    extra = 0


class VacationDaysOverrideInline(admin.TabularInline):
    model = VacationDaysOverride
    extra = 0
    radio_fields = {"type": admin.HORIZONTAL}


class FeatureFilter(admin.SimpleListFilter):
    title = _("feature")
    parameter_name = "feature"

    def lookups(self, request, model_admin):
        return [(choice.value, LABELS[choice]["label"]) for choice in FEATURES]

    def queryset(self, request, queryset):
        if value := self.value():
            queryset = queryset.filter(_features__overlap=[value])
        return queryset


@admin.register(User)
class UserAdmin(UserAdmin):
    form = UserChangeForm
    add_form = UserChangeForm

    list_display = (
        "email",
        "is_active",
        "is_admin",
        "working_time_model",
        "planning_hours_per_day",
        "last_login",
        "person",
        "specialist_field",
        "_features",
    )
    list_filter = (
        "is_active",
        "is_admin",
        "working_time_model",
        "specialist_field",
        FeatureFilter,
    )
    list_select_related = ["person__organization", "working_time_model"]
    fieldsets = add_fieldsets = [
        (
            None,
            {
                "fields": [
                    field.name
                    for field in User._meta.get_fields()
                    if field.editable and field.name not in {"password", "id"}
                ]
            },
        )
    ]
    radio_fields = {"language": admin.HORIZONTAL}
    raw_id_fields = ["person", "pinned_projects"]
    readonly_fields = ["last_login"]
    search_fields = ("email", "_short_name", "_full_name")
    ordering = ("-is_active", "email")
    filter_horizontal = ()
    inlines = [EmploymentInline, VacationDaysOverrideInline]


admin.site.unregister(Group)  # We are not using stock users or groups.


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    filter_horizontal = ["members"]


@admin.register(SpecialistField)
class SpecialistFieldAdmin(admin.ModelAdmin):
    pass
