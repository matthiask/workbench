from django.contrib import admin

from contacts.models import (
    Group,
    Organization,
    Person,
    EmailAddress,
    PhoneNumber,
    PostalAddress,
)


class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 0


class EmailAddressInline(admin.TabularInline):
    model = EmailAddress
    extra = 0


class PostalAddressInline(admin.TabularInline):
    model = PostalAddress
    extra = 0


class OrganizationAdmin(admin.ModelAdmin):
    filter_horizontal = ("groups",)
    list_display = ("name", "primary_contact")
    raw_id_fields = ("primary_contact",)
    search_fields = ("name", "notes")


class PersonAdmin(admin.ModelAdmin):
    filter_horizontal = ("groups",)
    inlines = [PhoneNumberInline, EmailAddressInline, PostalAddressInline]
    list_display = ("full_name", "organization", "primary_contact")
    raw_id_fields = ("organization", "primary_contact")
    search_fields = ("full_name", "notes")


admin.site.register(Group)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Person, PersonAdmin)
