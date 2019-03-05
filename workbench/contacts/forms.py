from collections import OrderedDict

from django import forms
from django.forms.models import inlineformset_factory
from django.template.defaultfilters import linebreaksbr
from django.utils.translation import ugettext_lazy as _

from workbench.contacts.models import (
    Group,
    Organization,
    Person,
    PhoneNumber,
    EmailAddress,
    PostalAddress,
)
from workbench.tools.forms import ModelForm, Picker, Textarea, WarningsForm


class OrganizationSearchForm(forms.Form):
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_("All groups"),
        label=_("Group"),
        widget=forms.Select(attrs={"class": "custom-select"}),
    )

    def filter(self, queryset):
        data = self.cleaned_data

        if data.get("g"):
            queryset = queryset.filter(groups=data.get("g"))
        return queryset


class OrganizationForm(ModelForm):
    user_fields = default_to_current_user = ("primary_contact",)

    class Meta:
        model = Organization
        fields = ("name", "notes", "primary_contact", "groups")
        widgets = {
            "name": Textarea(),
            "notes": Textarea(),
            "groups": forms.CheckboxSelectMultiple(),
        }


class PersonForm(WarningsForm, ModelForm):
    user_fields = default_to_current_user = ("primary_contact",)

    class Meta:
        model = Person
        fields = (
            "address",
            "given_name",
            "family_name",
            "salutation",
            "notes",
            "organization",
            "primary_contact",
            "groups",
        )
        widgets = {
            "notes": Textarea(),
            "organization": Picker(model=Organization),
            "groups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kwargs.pop("request")
        self.formsets = (
            OrderedDict(
                (
                    ("phonenumbers", PhoneNumberFormset(*args, **kwargs)),
                    ("emailaddresses", EmailAddressFormset(*args, **kwargs)),
                    ("postaladdresses", PostalAddressFormset(*args, **kwargs)),
                )
            )
            if self.instance.pk
            else OrderedDict()
        )

    def clean(self):
        data = super().clean()
        if not data.get("salutation"):
            self.add_warning(_("No salutation set. This will make newsletters ugly."))
        return data

    def is_valid(self):
        return all(
            [super().is_valid()]
            + [formset.is_valid() for formset in self.formsets.values()]
        )

    def save(self, commit=True):
        instance = super().save()
        for formset in self.formsets.values():
            formset.save()
        return instance


PhoneNumberFormset = inlineformset_factory(
    Person,
    PhoneNumber,
    fields=("type", "phone_number"),
    extra=0,
    widgets={
        "type": forms.TextInput(
            attrs={"class": "form-control short", "placeholder": _("type")}
        ),
        "phone_number": forms.TextInput(attrs={"class": "form-control"}),
    },
)

EmailAddressFormset = inlineformset_factory(
    Person,
    EmailAddress,
    fields=("type", "email"),
    extra=0,
    widgets={
        "type": forms.TextInput(
            attrs={"class": "form-control short", "placeholder": _("type")}
        ),
        "email": forms.TextInput(attrs={"class": "form-control"}),
    },
)


class PostalAddressForm(forms.ModelForm):
    class Meta:
        model = PostalAddress
        fields = (
            "type",
            "street",
            "house_number",
            "address_suffix",
            "postal_code",
            "city",
            "country",
            "postal_address_override",
        )
        widgets = {
            "type": forms.TextInput(
                attrs={"class": "form-control short", "placeholder": _("type")}
            ),
            "postal_address_override": Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }


PostalAddressFormset = inlineformset_factory(
    Person, PostalAddress, form=PostalAddressForm, extra=0
)


class PostalAddressSelectionForm(ModelForm):
    def add_postal_address_selection(self, *, organization=None, person=None):
        postal_addresses = []

        if person:
            postal_addresses.extend(
                (pa.id, linebreaksbr(pa.postal_address))
                for pa in PostalAddress.objects.filter(person=person)
            )

        if organization:
            postal_addresses.extend(
                (pa.id, linebreaksbr(pa.postal_address))
                for pa in PostalAddress.objects.filter(
                    person__organization=organization
                ).exclude(person=person)
            )

        if postal_addresses:
            self.fields["pa"] = forms.ModelChoiceField(
                PostalAddress.objects.all(),
                label=_("postal address"),
                help_text=_("The exact address can be edited later."),
                widget=forms.RadioSelect,
            )
            self.fields["pa"].choices = postal_addresses

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("pa"):
            instance.postal_address = self.cleaned_data["pa"].postal_address
        if commit:
            instance.save()
        return instance
