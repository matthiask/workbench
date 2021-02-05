from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from workbench.accounts.features import FEATURES, LABELS, F
from workbench.accounts.models import Team, User
from workbench.awt.models import Employment


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
            elif feature in current:
                ret["attrs"] = "checked"
            return ret

        context["widget"]["features"] = [
            checkbox(feature, **LABELS[feature]) for feature in FEATURES
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
        fields = "__all__"
        widgets = {"_features": FeaturesWidget}


class EmploymentInline(admin.TabularInline):
    model = Employment
    extra = 0


class UserAdmin(UserAdmin):
    form = UserChangeForm
    add_form = UserChangeForm

    list_display = (
        "email",
        "_short_name",
        "_full_name",
        "is_active",
        "working_time_model",
        "last_login",
        "person",
        "_features",
    )
    list_filter = ("is_active", "working_time_model")
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
                + ["signed_email"]
            },
        )
    ]
    radio_fields = {"language": admin.HORIZONTAL}
    raw_id_fields = ["person"]
    readonly_fields = ["signed_email", "last_login"]
    search_fields = ("email", "_short_name", "_full_name")
    ordering = ("email",)
    filter_horizontal = ()
    inlines = [EmploymentInline]


admin.site.register(User, UserAdmin)
admin.site.unregister(Group)  # We are not using stock users or groups.


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    filter_horizontal = ["members"]
