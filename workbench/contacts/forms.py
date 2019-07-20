from collections import OrderedDict

from django import forms
from django.forms.models import inlineformset_factory
from django.template.defaultfilters import linebreaksbr
from django.utils.translation import gettext_lazy as _, ngettext

from workbench.contacts.models import (
    EmailAddress,
    Group,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.tools.forms import Autocomplete, ModelForm, Textarea
from workbench.tools.xlsx import WorkbenchXLSXDocument


class OrganizationSearchForm(forms.Form):
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_("All groups"),
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data

        if data.get("g"):
            queryset = queryset.filter(groups=data.get("g"))
        return queryset


class PersonSearchForm(forms.Form):
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_("All groups"),
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data

        if data.get("g"):
            queryset = queryset.filter(groups=data.get("g"))
        return queryset

    def response(self, request, queryset):
        if request.GET.get("xlsx"):
            xlsx = WorkbenchXLSXDocument()
            xlsx.people(queryset)
            return xlsx.to_response("people.xlsx")


class OrganizationForm(ModelForm):
    user_fields = default_to_current_user = ("primary_contact",)

    class Meta:
        model = Organization
        fields = ("name", "is_private_person", "notes", "primary_contact", "groups")
        widgets = {
            "name": Textarea(),
            "notes": Textarea(),
            "groups": forms.CheckboxSelectMultiple(),
        }


class PersonForm(ModelForm):
    user_fields = default_to_current_user = ["primary_contact"]

    class Meta:
        model = Person
        fields = (
            "address",
            "given_name",
            "family_name",
            "address_on_first_name_terms",
            "salutation",
            "notes",
            "organization",
            "primary_contact",
            "groups",
            "is_archived",
        )
        widgets = {
            "notes": Textarea(),
            "organization": Autocomplete(model=Organization),
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
        if not data["salutation"]:
            self.add_warning(
                _("No salutation set. This will make newsletters ugly."),
                code="no-salutation",
            )
        elif len(data["salutation"].split()) < 2:
            self.add_warning(
                _("This does not look right. Please add a full salutation."),
                code="short-salutation",
            )
        if self.instance.pk and "organization" in self.changed_data:
            from workbench.deals.models import Deal
            from workbench.invoices.models import Invoice
            from workbench.projects.models import Project

            related = []
            deals = Deal.objects.filter(contact=self.instance).count()
            invoices = Invoice.objects.filter(contact=self.instance).count()
            projects = Project.objects.filter(contact=self.instance).count()

            for model, count in [
                (Deal, deals),
                (Invoice, invoices),
                (Project, projects),
            ]:
                if count:
                    related.append(
                        "%s %s"
                        % (
                            count,
                            ngettext(
                                model._meta.verbose_name,
                                model._meta.verbose_name_plural,
                                count,
                            ),
                        )
                    )

            if related:
                self.add_warning(
                    _(
                        "This person is the contact of the following related objects:"
                        " %s. Modifying this record may be more confusing than"
                        " archiving this one and creating a new record instead."
                    )
                    % ", ".join(related),
                    code="organization-update",
                )

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
    def add_postal_address_selection_if_empty(self, *, organization=None, person=None):
        if self.instance.postal_address:
            return

        postal_addresses = []

        if person:
            postal_addresses.extend(
                (pa.id, linebreaksbr(pa.postal_address))
                for pa in PostalAddress.objects.filter(person=person).select_related(
                    "person__organization"
                )
            )

        if organization and (not person or not postal_addresses):
            postal_addresses.extend(
                (pa.id, linebreaksbr(pa.postal_address))
                for pa in PostalAddress.objects.filter(
                    person__organization=organization
                )
                .exclude(person=person)
                .select_related("person__organization")
            )

        if postal_addresses:
            self.fields["pa"] = forms.ModelChoiceField(
                PostalAddress.objects.all(),
                label=_("postal address"),
                help_text=_("The exact address can be edited later."),
                widget=forms.RadioSelect,
            )
            self.fields["pa"].choices = postal_addresses
            self.fields.pop("postal_address", None)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("pa"):
            instance.postal_address = self.cleaned_data["pa"].postal_address
        if commit:
            instance.save()
        return instance
