from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


class UserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            'email', '_short_name', '_full_name', 'date_of_birth',
            'is_active', 'is_admin',
        )


class UserAdmin(UserAdmin):
    form = UserChangeForm
    add_form = UserChangeForm

    list_display = (
        'email', '_short_name', '_full_name', 'date_of_birth',
        'is_active', 'is_admin')
    list_filter = ('is_active', 'is_admin')
    fieldsets = (
        (None, {'fields': ('is_active', 'email')}),
        ('Personal info', {'fields': (
            '_short_name', '_full_name', 'date_of_birth',)}),
        ('Permissions', {'fields': ('is_admin',)}),
    )
    add_fieldsets = fieldsets
    search_fields = ('email', '_short_name', '_full_name')
    ordering = ('email',)
    filter_horizontal = ()


admin.site.register(User, UserAdmin)
admin.site.unregister(Group)  # We are not using stock users or groups.
