from workbench.contacts.models import (
    EmailAddress,
    Group,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.tools import admin


class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 0


class EmailAddressInline(admin.TabularInline):
    model = EmailAddress
    extra = 0


class PostalAddressInline(admin.TabularInline):
    model = PostalAddress
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    filter_horizontal = ("groups",)
    list_display = ("name", "primary_contact")
    raw_id_fields = ("primary_contact",)
    search_fields = ("name", "notes")


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    filter_horizontal = ("groups",)
    inlines = [PhoneNumberInline, EmailAddressInline, PostalAddressInline]
    list_display = ["given_name", "family_name", "organization", "primary_contact"]
    list_filter = ["is_archived"]
    raw_id_fields = ["organization", "primary_contact"]
    search_fields = ["given_name", "family_name", "notes"]


@admin.register(Group)
class GroupAdmin(admin.ReadWriteModelAdmin):
    pass
