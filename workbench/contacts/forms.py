import datetime as dt
import json
from collections import OrderedDict

from django import forms
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Func, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.forms.models import inlineformset_factory
from django.http import Http404
from django.template.defaultfilters import linebreaksbr
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _, ngettext

from workbench.accounts.models import User
from workbench.contacts.merge import (
    contact_of,
    merge_errors,
    merge_organizations,
    merge_people,
    merge_warnings,
)
from workbench.contacts.models import (
    ADDRESS_FIELDS,
    EmailAddress,
    Group,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
    in_group_q,
    organization_postal_addresses,
    postal_address_choices,
    unarchive_organization,
    update_organization_archival,
)
from workbench.tools.forms import (
    Autocomplete,
    Form,
    ModelForm,
    SuggestionsInput,
    Textarea,
    add_prefix,
)
from workbench.tools.models import ProtectedError, SlowCollector
from workbench.tools.vcard import person_to_vcard, render_vcard_response
from workbench.tools.xlsx import WorkbenchXLSXDocument


def group_choices():
    """Groups for filters, archived groups separately at the end"""
    groups = {False: [], True: []}
    for group in Group.objects.all():
        groups[group.is_archived].append((group.pk, group.title))
    return [
        ("", _("All groups")),
        *[
            (label, groups[archived])
            for archived, label in [(False, _("Active")), (True, _("Archived"))]
            if groups[archived]
        ],
    ]


class GroupSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=[
            ("", _("Active")),
            ("archived", _("Archived")),
            ("all", _("All")),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if q := data.get("q"):
            queryset = queryset.filter(title__icontains=q)
        if data.get("s") == "archived":
            queryset = queryset.filter(is_archived=True)
        elif data.get("s") != "all":
            queryset = queryset.filter(is_archived=False)
        return queryset.annotate(
            people_count=_people_count(is_archived=False),
            organizations_count=_member_count(Organization, is_archived=False),
            archived_people_count=_people_count(is_archived=True),
            archived_organizations_count=_member_count(Organization, is_archived=True),
        ).order_by(*Group._meta.ordering)


def _member_count(model, *, is_archived):
    """Members of the group, counted in a subquery: joining people and
    organizations at once multiplies their rows"""
    through = model.groups.through
    member = model._meta.model_name
    return Coalesce(
        Subquery(
            through.objects
            .filter(group=OuterRef("pk"), **{f"{member}__is_archived": is_archived})
            .order_by()
            .values("group")
            .annotate(count=Count("pk"))
            .values("count")
        ),
        0,
    )


def _people_count(*, is_archived):
    """People in the group, also through their organization"""
    return Coalesce(
        Subquery(
            Person.objects
            .filter(in_group_q(OuterRef(OuterRef("pk"))), is_archived=is_archived)
            .order_by()
            .annotate(count=Func("pk", function="COUNT"))
            .values("count")
        ),
        0,
    )


@add_prefix("modal")
class GroupForm(ModelForm):
    class Meta:
        model = Group
        fields = ["title", "applies_to_organizations", "is_pinned", "is_archived"]

    def clean_title(self):
        """The APIs find groups by their title"""
        title = self.cleaned_data["title"]
        if Group.objects.filter(title__iexact=title).exclude(pk=self.instance.pk):
            raise forms.ValidationError(_("A group with this title exists already."))
        return title

    def save(self, *, commit=True):
        instance = super().save()
        if "applies_to_organizations" in self.changed_data:
            if instance.applies_to_organizations:
                instance.move_people_to_organizations()
            else:
                instance.move_organizations_to_people()
        return instance


def recent_projects_or_deals(field, *, since=None):
    """Filter for contacts with projects or deals created since the date,
    the last 5 years by default; ``field`` is the field of projects and deals
    pointing to them"""
    from workbench.deals.models import Deal
    from workbench.projects.models import Project

    cutoff = (
        timezone.make_aware(dt.datetime.combine(since, dt.time.min))
        if since
        else timezone.now() - dt.timedelta(days=5 * 366)
    )
    return Q(id__in=Deal.objects.filter(created_at__gte=cutoff).values(field)) | Q(
        id__in=Project.objects.filter(created_at__gte=cutoff).values(field)
    )


class OrganizationSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=[
            ("", _("Active")),
            ("all", _("All")),
            (
                _("Defined search"),
                [
                    (
                        "any-projects-deals",
                        _("Any projects or deals in the last 5 years"),
                    ),
                    ("no-group", _("No group")),
                    ("no-people", _("No active people")),
                ],
            ),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_("All groups"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["g"].choices = group_choices()

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("s") != "all":
            queryset = queryset.active()
        if data.get("s") == "any-projects-deals":
            queryset = queryset.filter(recent_projects_or_deals("customer"))
        elif data.get("s") == "no-group":
            queryset = queryset.exclude(groups__is_archived=False)
        elif data.get("s") == "no-people":
            queryset = queryset.exclude(people__is_archived=False)
        return self.apply_renamed(queryset, "g", "groups")

    def archived_in_group(self):
        """Archived organizations aren't listed unless asked for, the number is
        shown"""
        data = self.cleaned_data
        if (group := data.get("g")) and not data.get("s"):
            return Organization.objects.filter(groups=group, is_archived=True).count()
        return 0


class PersonSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=[
            ("", _("Active")),
            ("all", _("All")),
            (
                _("Defined search"),
                [
                    (
                        "any-projects-deals",
                        _("Any projects or deals in the last 5 years"),
                    ),
                    (
                        "missing-salutation",
                        _("Missing salutation (only w/email)"),
                    ),
                    (
                        "missing-email",
                        _("Missing email address"),
                    ),
                    (
                        "missing-postal-address",
                        _("Missing or incomplete postal address"),
                    ),
                    ("no-group", _("No group")),
                ],
            ),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    g = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label=_("All groups"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    primary_contact = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["primary_contact"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )
        self.fields["g"].choices = group_choices()

    def archived_in_group(self):
        """Archived people of the group aren't listed unless asked for, the
        number is shown"""
        data = self.cleaned_data
        if (group := data.get("g")) and not data.get("s"):
            return Person.objects.in_group(group).filter(is_archived=True).count()
        return 0

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))

        if not data.get("s"):
            queryset = queryset.active()
        elif data.get("s") == "any-projects-deals":
            queryset = queryset.filter(recent_projects_or_deals("contact")).active()
        elif data.get("s") == "missing-salutation":
            queryset = queryset.active().filter(
                salutation="", emailaddresses__isnull=False
            )
        elif data.get("s") == "missing-email":
            queryset = queryset.active().filter(emailaddresses__isnull=True)
        elif data.get("s") == "missing-postal-address":
            queryset = queryset.active().without_complete_postal_address()
        elif data.get("s") == "no-group":
            queryset = queryset.active().without_groups()

        if group := data.get("g"):
            queryset = queryset.in_group(group)
        queryset = self.apply_owned_by(queryset, attribute="primary_contact")
        active_groups = Group.objects.filter(is_archived=False)
        return queryset.select_related(
            "organization", "primary_contact"
        ).prefetch_related(
            Prefetch("groups", queryset=active_groups),
            Prefetch(
                "organization__groups",
                queryset=active_groups.filter(applies_to_organizations=True),
            ),
        )

    def response(self, request, queryset):
        if request.GET.get("export") == "xlsx":
            xlsx = WorkbenchXLSXDocument()
            xlsx.people(queryset)
            # E.g. people-christmas-mailing-2026-11-04.xlsx
            group = self.cleaned_data.get("g")
            name = "-".join(
                filter(
                    None,
                    [
                        str(slugify(_("people"))),
                        slugify(group.title) if group else "",
                        dt.date.today().isoformat(),
                    ],
                )
            )
            return xlsx.to_response(f"{name}.xlsx")

        if request.GET.get("export") == "vcard":
            return render_vcard_response(
                request,
                "\n".join(
                    person_to_vcard(person).serialize()
                    for person in queryset.prefetch_related(
                        "phonenumbers", "emailaddresses", "postaladdresses"
                    )[: settings.BATCH_MAX_ITEMS]
                ),
            )
        return None


class OrganizationForm(ModelForm):
    user_fields = default_to_current_user = ("primary_contact",)

    class Meta:
        model = Organization
        # Archiving comes first, it shouldn't need searching for
        fields = (
            "is_archived",
            "name",
            "is_private_person",
            "notes",
            "primary_contact",
            "email",
            "accounts_payable_email",
            "phone_number",
            "default_billing_address",
            "groups",
        )
        widgets = {
            "name": Textarea(),
            "notes": Textarea(),
            "default_billing_address": Textarea(),
            "groups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = _offered_groups(
            self.instance.groups.values("pk") if self.instance.pk else []
        )

    def _archiving(self):
        return (
            self.instance.pk
            and "is_archived" in self.changed_data
            and self.cleaned_data.get("is_archived")
        )

    def clean(self):
        data = super().clean()
        if self._archiving() and (warning := self.instance.archive_warning()):
            self.add_warning(warning, code="archive-people")
        return data

    def save(self, *, commit=True):
        archiving = self._archiving()
        instance = super().save(commit=commit)
        if archiving and (count := instance.archive_people()):
            messages.info(
                self.request,
                ngettext(
                    "%(count)s person has been archived with the organization.",
                    "%(count)s people have been archived with the organization.",
                    count,
                )
                % {"count": count},
            )
        return instance


def _offered_groups(current):
    """Archived groups only for contacts already in them"""
    return Group.objects.filter(Q(is_archived=False) | Q(pk__in=current))


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
            self.protected = True
            if self.request.method == "GET":
                messages.info(self.request, self.protected_message())
        else:
            self.protected = False

    def protected_message(self):
        return _(
            "This organization has related objects. It is therefore not"
            " possible to delete it, but you may merge it into a different"
            " organization. Alternatively, you can also archive the"
            " organization."
        )

    def clean(self):
        data = super().clean()
        if self.protected:
            self.add_error(None, self.protected_message())
        return data

    def delete(self):
        self.instance.delete()


@add_prefix("modal")
class OrganizationMergeForm(Form):
    """Merge a duplicate organization into the organization to keep, see
    merge_organizations()"""

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)
        self.fields["into"] = forms.ModelChoiceField(
            Organization.objects.exclude(pk=self.instance.pk),
            widget=Autocomplete(model=Organization),
            label=_("merge into"),
            help_text=_(
                "Moves people, projects, deals, invoices and groups to this"
                " organization, e.g. if it exists twice. This organization"
                " is deleted."
            ),
        )

    def save(self):
        keep = self.cleaned_data["into"]
        merge_organizations(duplicate=self.instance, keep=keep)
        return keep


class OrganizationPostalAddressForm(Form):
    """Change an address of the organization's people for all of them, e.g.
    when it moves (``?address=`` is one of the postal addresses)"""

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        pk = kwargs.pop("address", None)
        super().__init__(*args, **kwargs)
        pk = str(pk or self.request.GET.get("address"))
        self.address = next(
            (
                entry
                for entry in organization_postal_addresses(self.instance)
                if any(str(address.pk) == pk for address in entry["addresses"])
            ),
            None,
        )
        if not self.address:
            raise Http404
        self.fields.update(
            forms.fields_for_model(
                PostalAddress,
                fields=ADDRESS_FIELDS,
                widgets=PostalAddressForm.Meta.widgets,
            )
        )
        self.initial.update(self.address["fields"])
        self.fields["people"] = forms.TypedMultipleChoiceField(
            label=_("people"),
            choices=[
                (person.pk, person.full_name) for person in self.address["people"]
            ],
            coerce=int,
            widget=forms.CheckboxSelectMultiple,
            initial=[person.pk for person in self.address["people"]],
            help_text=_("The address is changed for the selected people."),
        )

    def save(self):
        people = set(self.cleaned_data["people"])
        with transaction.atomic():
            for address in self.address["addresses"]:
                if address.person_id in people:
                    for field in ADDRESS_FIELDS:
                        setattr(address, field, self.cleaned_data[field])
                    address.save()
            # Updates the full text search
            for person in self.address["people"]:
                if person.pk in people:
                    person.save()
        return self.instance


class PersonDeleteForm(ModelForm):
    class Meta:
        model = Person
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        collector = SlowCollector(using=self.instance._state.db)
        try:
            collector.collect([self.instance])
        except ProtectedError:
            self.protected = True
            if self.request.method == "GET":
                messages.info(self.request, self.protected_message())
        else:
            self.protected = False

    def protected_message(self):
        return _(
            "This person is linked to a user. It is therefore not possible"
            " to delete them, but you may merge them into a different"
            " person. Alternatively, you can also archive the person."
        )

    def clean(self):
        data = super().clean()
        if self.protected:
            self.add_error(None, self.protected_message())
        elif related := contact_of(self.instance):
            self.add_warning(
                _(
                    "%(person)s is the contact of %(related)s, which lose"
                    " their contact when deleting them. Merge them into a"
                    " different person instead if they exist twice."
                )
                % {"person": self.instance, "related": ", ".join(related)},
                code="lose-contact",
            )
        return data

    def delete(self):
        self.instance.delete()


@add_prefix("modal")
class PersonMergeForm(Form):
    """Merge a duplicate into the person to keep, see merge_people()"""

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)
        self.fields["into"] = forms.ModelChoiceField(
            Person.objects.exclude(pk=self.instance.pk),
            widget=Autocomplete(model=Person),
            label=_("merge into"),
            help_text=_(
                "Moves projects, deals, invoices, contact details and groups"
                " to this person, e.g. if someone exists twice. This person"
                " is deleted."
            ),
        )

    def clean(self):
        data = super().clean()
        if keep := data.get("into"):
            for error in merge_errors(duplicate=self.instance, keep=keep):
                self.add_error("into", error)
            for message, code in merge_warnings(duplicate=self.instance, keep=keep):
                self.add_warning(message, code=code)
        return data

    def save(self):
        keep = self.cleaned_data["into"]
        merge_people(duplicate=self.instance, keep=keep)
        return keep


def organization_update_warning(person):
    """Warning (``organization-update``) when moving a person who is the
    contact of related objects to another organization, or None"""
    from workbench.deals.models import Deal
    from workbench.invoices.models import Invoice
    from workbench.projects.models import Project

    related = [
        f"{count} {ngettext(model._meta.verbose_name, model._meta.verbose_name_plural, count)}"
        for model in [Invoice, Project, Deal]
        if (count := model.objects.filter(contact=person).count())
    ]
    if not related:
        return None
    return _(
        "This person is the contact of the following related objects:"
        " %s. Modifying this record may be more confusing than"
        " archiving this one and creating a new record instead."
    ) % ", ".join(related)


class PersonForm(ModelForm):
    user_fields = default_to_current_user = ["primary_contact"]

    class Meta:
        model = Person
        # Archiving comes first, it shouldn't need searching for
        fields = (
            "is_archived",
            "address",
            "given_name",
            "family_name",
            "address_on_first_name_terms",
            "salutation",
            "date_of_birth",
            "year_of_birth_unknown",
            "notes",
            "organization",
            "primary_contact",
            "groups",
        )
        widgets = {
            "notes": Textarea(),
            "organization": Autocomplete(model=Organization),
            "groups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs["request"]
        initial = kwargs.setdefault("initial", {})
        if organization := request.GET.get("organization"):
            initial["organization"] = organization

        super().__init__(*args, **kwargs)
        # Groups which apply to organizations are edited through people too
        current = (
            [group.pk for group in self.instance.all_groups()]
            if self.instance.pk
            else []
        )
        self.initial["groups"] = current
        self.fields["groups"].queryset = _offered_groups(current)
        kwargs.pop("request")
        self.formsets = (
            OrderedDict((
                ("phonenumbers", PhoneNumberFormset(*args, **kwargs)),
                ("emailaddresses", EmailAddressFormset(*args, **kwargs)),
                ("postaladdresses", PostalAddressFormset(*args, **kwargs)),
            ))
            if self.instance.pk
            else OrderedDict()
        )

    def clean(self):
        data = super().clean()
        if data.get("year_of_birth_unknown") and not data.get("date_of_birth"):
            self.add_error(
                "date_of_birth",
                _("Enter any year and the day and the month of the birthday."),
            )
        if data.get("salutation") and len(data.get("salutation").split()) < 2:
            self.add_warning(
                _("This does not look right. Please add a full salutation."),
                code="short-salutation",
            )
        if (
            self.instance.pk
            and "organization" in self.changed_data
            and (warning := organization_update_warning(self.instance))
        ):
            self.add_warning(warning, code="organization-update")

        return data

    def colleague_postal_addresses(self):
        """Addresses of colleagues, to be copied in the postal addresses
        formset"""
        if not (self.instance.pk and self.instance.organization):
            return []
        addresses = organization_postal_addresses(
            self.instance.organization, exclude_person=self.instance
        )
        for address in addresses:
            fields = {**address["fields"], "type": address["type"]}
            # Overrides often contain the name of the colleague
            for person in address["people"]:
                fields["postal_address_override"] = fields[
                    "postal_address_override"
                ].replace(person.full_name, self.instance.full_name)
            address["initial"] = json.dumps(fields)
        return addresses

    def is_valid(self, *, ignore_warnings=False):
        return all(
            [super().is_valid(ignore_warnings=ignore_warnings)]
            + [formset.is_valid() for formset in self.formsets.values()]
        )

    def save(self, *, commit=True):
        instance = super().save()
        if instance.organization:
            self._save_organization_groups(instance)
        for formset in self.formsets.values():
            formset.save()
        if "is_archived" in self.changed_data:
            organization = update_organization_archival(instance)
        elif "organization" in self.changed_data:
            organization = unarchive_organization(instance)
        else:
            organization = None
        if organization:
            messages.info(
                self.request,
                (
                    _("%(organization)s has been archived with its last person.")
                    if organization.is_archived
                    else _("%(organization)s has been unarchived.")
                )
                % {"organization": organization.name},
            )
        return instance

    def _save_organization_groups(self, instance):
        """Groups which apply to organizations go to the organization. Groups
        unchecked are only removed from the organization if it is the same
        as before, the form showed its groups"""
        groups = self.cleaned_data["groups"]
        organization_groups = [
            group for group in groups if group.applies_to_organizations
        ]
        if "organization" not in self.changed_data:
            unchecked = set(self.initial["groups"]) - {group.pk for group in groups}
            instance.organization.groups.remove(
                *Group.objects.filter(pk__in=unchecked, applies_to_organizations=True)
            )
        instance.organization.groups.add(*organization_groups)
        instance.groups.remove(*organization_groups)


PhoneNumberFormset = inlineformset_factory(
    Person,
    PhoneNumber,
    fields=("type", "phone_number"),
    extra=0,
    widgets={
        "type": SuggestionsInput(
            PhoneNumber.TYPES,
            attrs={"class": "form-control short", "placeholder": _("type")},
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
        "type": SuggestionsInput(
            EmailAddress.TYPES,
            attrs={"class": "form-control short", "placeholder": _("type")},
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
            "type": SuggestionsInput(
                PostalAddress.TYPES,
                attrs={"class": "form-control short", "placeholder": _("type")},
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
        postal_addresses = postal_address_choices(
            organization=organization, person=person, for_billing=for_billing
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
                _("The postal address should probably be at least three lines long."),
                code="short-postal-address",
            )

        return data


@add_prefix("modal")
class PersonAutocompleteForm(forms.Form):
    person = forms.ModelChoiceField(
        queryset=Person.objects.all(), widget=Autocomplete(model=Person), label=""
    )
