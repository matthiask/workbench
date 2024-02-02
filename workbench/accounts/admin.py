from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from workbench.accounts.models import User


class UserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email", "_short_name", "_full_name", "is_active", "is_admin")


@admin.register(User)
class UserAdmin(UserAdmin):
    form = UserChangeForm
    add_form = UserChangeForm

    list_display = ("email", "_short_name", "_full_name", "is_active", "is_admin")
    list_filter = ("is_active", "is_admin")
    fieldsets = (
        (None, {"fields": ("email", ("is_active", "is_admin"))}),
        ("Personal info", {"fields": ("_short_name", "_full_name")}),
    )
    add_fieldsets = fieldsets
    search_fields = ("email", "_short_name", "_full_name")
    ordering = ("email",)
    filter_horizontal = ()


admin.site.unregister(Group)  # We are not using stock users or groups.
