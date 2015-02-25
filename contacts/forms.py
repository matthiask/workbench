from django import forms
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext_lazy as _

from contacts.models import (
    Group, Organization, Person, PhoneNumber, EmailAddress, PostalAddress)
from tools.forms import ModelForm, Picker, Textarea


class OrganizationSearchForm(forms.Form):
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_('All groups'),
        label=_('Group'),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )


class OrganizationForm(ModelForm):
    user_fields = ('primary_contact',)

    class Meta:
        model = Organization
        fields = ('name', 'notes', 'primary_contact', 'groups')
        widgets = {
            'name': Textarea(),
            'notes': Textarea(),
            'groups': forms.CheckboxSelectMultiple(),
        }


class PersonForm(ModelForm):
    user_fields = ('primary_contact',)

    class Meta:
        model = Person
        fields = (
            'full_name', 'address', 'notes', 'organization', 'primary_contact',
            'groups')
        widgets = {
            'notes': Textarea(),
            'organization': Picker(model=Organization),
            'groups': forms.CheckboxSelectMultiple(),
        }


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
