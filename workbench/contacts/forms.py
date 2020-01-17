from collections import OrderedDict

from django import forms
from django.forms.models import inlineformset_factory
from django.template.defaultfilters import linebreaksbr
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _, ngettext

from workbench.contacts.models import (
    EmailAddress,
    Group,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea, add_prefix
from workbench.tools.models import ProtectedError, SlowCollector
from workbench.tools.substitute_with import substitute_with
from workbench.tools.xlsx import WorkbenchXLSXDocument


class OrganizationSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("search")}
        ),
        label="",
    )
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_("All groups"),
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        return self.apply_renamed(queryset, "g", "groups")


class PersonSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("search")}
        ),
        label="",
    )
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_("All groups"),
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q")).active()
        return self.apply_renamed(queryset, "g", "groups").select_related(
            "organization"
        )

    def response(self, request, queryset):
        if request.GET.get("xlsx"):
            xlsx = WorkbenchXLSXDocument()
            xlsx.people(queryset)
            return xlsx.to_response("people.xlsx")


class OrganizationForm(ModelForm):
    user_fields = default_to_current_user = ("primary_contact",)

    class Meta:
        model = Organization
        fields = (
            "name",
            "is_private_person",
            "notes",
            "primary_contact",
            "default_billing_address",
            "groups",
        )
        widgets = {
            "name": Textarea(),
            "notes": Textarea(),
            "default_billing_address": Textarea(),
            "groups": forms.CheckboxSelectMultiple(),
        }


class OrganizationDeleteForm(ModelForm):
    class Meta:
        model = Organization
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        collector = SlowCollector(using=self.instance._state.db)
        try:
            collector.collect([self.instance])
        except ProtectedError:
            self.fields["substitute_with"] = forms.ModelChoiceField(
                Organization.objects.exclude(pk=self.instance.pk),
                widget=Autocomplete(model=Organization),
                label=_("substitute with"),
            )

    def delete(self):
        if "substitute_with" in self.fields:
            substitute_with(
                to_delete=self.instance, instance=self.cleaned_data["substitute_with"]
            )
        else:
            self.instance.delete()


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
            "date_of_birth",
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
        request = kwargs["request"]
        initial = kwargs.setdefault("initial", {})
        if request.GET.get("organization"):
            initial["organization"] = request.GET["organization"]

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
            from workbench.invoices.models import Invoice
            from workbench.projects.models import Project

            related = []
            invoices = Invoice.objects.filter(contact=self.instance).count()
            projects = Project.objects.filter(contact=self.instance).count()

            for model, count in [
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
    def add_postal_address_selection_if_empty(
        self, *, organization=None, person=None, for_billing=False
    ):
        postal_addresses = []

        if person:
            if (
                for_billing
                and person.organization
                and person.organization.default_billing_address
            ):
                postal_addresses.append(
                    (
                        _("default billing address"),
                        person.organization.default_billing_address,
                    )
                )
            postal_addresses.extend(
                (pa.type, pa.postal_address)
                for pa in PostalAddress.objects.filter(person=person).select_related(
                    "person__organization"
                )
            )

        if organization and (not person or not postal_addresses):
            if for_billing and organization.default_billing_address:
                postal_addresses.append(
                    (_("default billing address"), organization.default_billing_address)
                )
            postal_addresses.extend(
                (pa.type, pa.postal_address)
                for pa in PostalAddress.objects.filter(
                    person__organization=organization
                )
                .exclude(person=person)
                .select_related("person__organization")
            )

        if postal_addresses:
            self.fields["postal_address"].help_text = format_html(
                '<strong>{}</strong><br><div class="'
                ' list-group list-group-horizontal flex-wrap">{}</div>',
                _("Select one of the following addresses:"),
                format_html_join(
                    "",
                    '<span class="list-group-item list-group-item-action w-auto"'
                    ' data-field-value="{}"><strong>{}</strong><br>{}</span>',
                    [(pa, type, linebreaksbr(pa)) for type, pa in postal_addresses],
                ),
            )
            # repr(postal_addresses)

    def clean(self):
        data = super().clean()

        postal_address = data.get("postal_address", "")
        if len(postal_address.strip().splitlines()) < 3:
            self.add_warning(
                _(
                    "The postal address should probably be at least three"
                    " lines long."
                ),
                code="short-postal-address",
            )

        return data


@add_prefix("modal")
class PersonAutocompleteForm(forms.Form):
    person = forms.ModelChoiceField(
        queryset=Person.objects.all(), widget=Autocomplete(model=Person), label=""
    )
