from django.contrib import admin

from contacts.models import (
    Group, Organization, Person, EmailAddress, PhoneNumber, PostalAddress)


class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 0


class EmailAddressInline(admin.TabularInline):
    model = EmailAddress
    extra = 0


class PostalAddressInline(admin.TabularInline):
    model = PostalAddress
    extra = 0


admin.site.register(Group)
admin.site.register(
    Organization,
    filter_horizontal=('groups',),
    raw_id_fields=('primary_contact',),
)
admin.site.register(
    Person,
    inlines=[PhoneNumberInline, EmailAddressInline, PostalAddressInline],
    raw_id_fields=('organization', 'primary_contact'),
)
