from collections import OrderedDict

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

    def filter(self, queryset):
        if not self.is_valid():
            return queryset

        data = self.cleaned_data

        if data.get('g'):
            queryset = queryset.filter(groups=data.get('g'))
        return queryset


class OrganizationForm(ModelForm):
    user_fields = default_to_current_user = ('primary_contact',)

    class Meta:
        model = Organization
        fields = ('name', 'notes', 'primary_contact', 'groups')
        widgets = {
            'name': Textarea(),
            'notes': Textarea(),
            'groups': forms.CheckboxSelectMultiple(),
        }


class PersonForm(ModelForm):
    user_fields = default_to_current_user = ('primary_contact',)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kwargs.pop('request')
        self.formsets = OrderedDict((
            ('phonenumbers', PhoneNumberFormset(*args, **kwargs)),
            ('emailaddresses', EmailAddressFormset(*args, **kwargs)),
            ('postaladdresses', PostalAddressFormset(*args, **kwargs)),
        )) if self.instance.pk else OrderedDict()

    def is_valid(self):
        return all(
            [super().is_valid()] +
            [formset.is_valid() for formset in self.formsets.values()])

    def save(self, commit=True):
        instance = super().save()
        for formset in self.formsets.values():
            formset.save()
        return instance


PhoneNumberFormset = inlineformset_factory(
    Person,
    PhoneNumber,
    fields=('type', 'phone_number'),
    extra=0)

EmailAddressFormset = inlineformset_factory(
    Person,
    EmailAddress,
    fields=('type', 'email'),
    extra=0)


class PostalAddressForm(forms.ModelForm):
    class Meta:
        model = PostalAddress
        fields = ('type', 'postal_address')
        widgets = {
            'postal_address': Textarea(attrs={'rows': 6}),
        }

PostalAddressFormset = inlineformset_factory(
    Person,
    PostalAddress,
    form=PostalAddressForm,
    extra=0)
