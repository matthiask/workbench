from django import forms
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext_lazy as _

from contacts.models import (
    Group, Person, PhoneNumber, EmailAddress, PostalAddress)


class OrganizationSearchForm(forms.Form):
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_('All groups'),
        label=_('Group'),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )


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
