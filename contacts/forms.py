from django.forms.models import inlineformset_factory

from contacts.models import (
    Person, PhoneNumber, EmailAddress, PostalAddress)


PhoneNumberFormset = inlineformset_factory(
    Person,
    PhoneNumber,
    extra=2)

EmailAddressFormset = inlineformset_factory(
    Person,
    EmailAddress,
    extra=2)

PostalAddressFormset = inlineformset_factory(
    Person,
    PostalAddress,
    extra=2)
