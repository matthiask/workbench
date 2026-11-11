import itertools
import re
from urllib.parse import urlencode

import phonenumbers
from django.db import models
from django.db.models import Exists, OuterRef, Q, Sum
from django.db.models.functions import Lower
from django.utils.functional import cached_property
from django.utils.translation import gettext, gettext_lazy as _
from django_countries.fields import CountryField

from workbench.accounts.models import User
from workbench.tools.formats import Z2, local_date_format
from workbench.tools.models import Model, SearchQuerySet
from workbench.tools.search import refresh_fts
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


@model_urls
class Group(Model):
    open_in_modal = True

    title = models.CharField(_("title"), max_length=100)
    is_archived = models.BooleanField(
        _("is archived"),
        default=False,
        help_text=_(
            "People only in archived groups are archived automatically after"
            " five years without use. Groups don't keep organizations without"
            " active people."
        ),
    )

    applies_to_organizations = models.BooleanField(
        _("applies to organizations"),
        default=False,
        help_text=_(
            "For example industries: people are in the group through their"
            " organization, changes on people go to the organization."
        ),
    )

    class Meta:
        constraints = [
            # The APIs find groups by their title, GroupForm validates it
            models.UniqueConstraint(Lower("title"), name="contacts_group_unique_title")
        ]
        ordering = ("title",)
        verbose_name = _("group")
        verbose_name_plural = _("groups")

    def __str__(self):
        return self.title

    def move_people_to_organizations(self):
        """People with an organization are in groups which apply to
        organizations through their organization"""
        memberships = Person.groups.through.objects.filter(
            group=self, person__organization__isnull=False
        )
        self.organization_set.add(
            *Organization.objects.filter(
                people__in=memberships.values("person")
            ).distinct()
        )
        memberships.delete()

    def move_organizations_to_people(self):
        """Groups which don't apply to organizations anymore keep their
        members: the people of the organizations join them"""
        self.person_set.add(
            *Person.objects.filter(organization__groups=self).exclude(groups=self)
        )
        self.organization_set.clear()

    def get_absolute_url(self):
        # Groups are lists of people
        return Person.urls["list"] + f"?g={self.pk}"


class OrganizationQuerySet(SearchQuerySet):
    def active(self):
        return self.filter(is_archived=False)


@model_urls
class Organization(Model):
    is_archived = models.BooleanField(
        _("is archived"),
        default=False,
        help_text=_("It is preferrable to archive records instead of deleting them."),
    )
    name = models.TextField(_("name"))
    is_private_person = models.BooleanField(_("is private person"), default=False)
    notes = models.TextField(_("notes"), blank=True)
    primary_contact = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("primary contact"),
    )
    default_billing_address = models.TextField(
        _("default billing address"),
        blank=True,
        help_text=_(
            "Mainly useful for organizations with a centralized"
            " accounts payable departement."
        ),
    )
    email = models.EmailField(
        _("email address"),
        blank=True,
        help_text=_(
            "Central address, e.g. info@. It's shown on the organization's"
            " people too, don't add it to them."
        ),
    )
    accounts_payable_email = models.EmailField(
        _("accounts payable email address"),
        blank=True,
        help_text=_("Optional, e.g. for invoices and payment reminders."),
    )
    groups = models.ManyToManyField(Group, verbose_name=_("groups"), blank=True)

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        ordering = ("name",)
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

    def __str__(self):
        parts = [self.name.replace("\n", " ")]
        if self.is_archived:
            parts.append(gettext("(archived)"))
        return " ".join(parts)

    def save(self, *args, **kwargs):
        renamed = (
            self.pk
            and Organization.objects.filter(pk=self.pk).exclude(name=self.name).exists()
        )
        super().save(*args, **kwargs)
        if renamed:
            self.refresh_related_fts()

    save.alters_data = True

    def refresh_related_fts(self):
        """The search texts of related objects contain the name"""
        from workbench.deals.models import Deal
        from workbench.invoices.models import Invoice
        from workbench.offers.models import Offer
        from workbench.projects.models import Campaign, Project

        refresh_fts(self.people.all())
        refresh_fts(Campaign.objects.filter(customer=self))
        refresh_fts(Project.objects.filter(customer=self))
        refresh_fts(Offer.objects.filter(project__customer=self))
        refresh_fts(Deal.objects.filter(customer=self))
        refresh_fts(Invoice.objects.filter(customer=self))

    @classmethod
    def allow_delete(cls, instance, request):
        return None

    def recent_projects(self):
        return self.project_set.select_related("owned_by")[:10]

    def recent_invoices(self):
        return self.invoice_set.select_related("owned_by")[:10]

    def postal_addresses(self):
        return organization_postal_addresses(self)

    def recent_offers(self):
        from workbench.offers.models import Offer

        return Offer.objects.filter(project__customer=self).select_related(
            "project", "owned_by"
        )[:10]

    @cached_property
    def statistics(self):
        from workbench.reporting.project_budget_statistics import (
            project_budget_statistics,
        )
        from workbench.reporting.squeeze import gross_margin_components

        pbs = project_budget_statistics(self.project_set.all())["overall"]
        gross_margin = sum(
            (
                row["invoiced"]
                for row in gross_margin_components(self.project_set.all()).values()
            ),
            Z2,
        )

        invoices = (
            self.invoice_set
            .invoiced()
            .filter(project__isnull=True)
            .order_by()
            .aggregate(Sum("total_excl_tax"), Sum("third_party_costs"))
        )

        pbs["invoiced"] += invoices["total_excl_tax__sum"] or Z2
        pbs["third_party_costs"] += invoices["third_party_costs__sum"] or Z2
        gross_margin += (invoices["total_excl_tax__sum"] or Z2) - (
            invoices["third_party_costs__sum"] or Z2
        )

        pbs["gross_margin_per_hour"] = (
            gross_margin / pbs["hours"] if pbs["hours"] else None
        )
        return pbs


class PersonQuerySet(SearchQuerySet):
    def active(self):
        return self.filter(is_archived=False)

    def in_group(self, group):
        """People in the group, also through their organization if the group
        applies to organizations"""
        return self.filter(in_group_q(group))

    def without_complete_postal_address(self):
        """People without a postal address with street, postal code and city
        (or one which is overridden completely), e.g. for mailings"""
        return self.exclude(
            Exists(
                PostalAddress.objects.filter(person=OuterRef("pk")).filter(
                    ~Q(postal_address_override="")
                    | (~Q(street="") & ~Q(postal_code="") & ~Q(city=""))
                )
            )
        )

    def without_groups(self):
        """People in no active group, also not through their organization"""
        return self.exclude(groups__is_archived=False).exclude(
            organization__in=Organization.objects.filter(
                groups__is_archived=False, groups__applies_to_organizations=True
            )
        )


def in_group_q(group):
    """``group`` may be a group or an expression (e.g. ``OuterRef``)"""
    return Q(
        id__in=Person.groups.through.objects.filter(group=group).values("person")
    ) | Q(
        organization__in=Organization.groups.through.objects.filter(
            group=group, group__applies_to_organizations=True
        ).values("organization")
    )


@model_urls
class Person(Model):
    is_archived = models.BooleanField(
        _("is archived"),
        default=False,
        help_text=_("It is preferrable to archive records instead of deleting them."),
    )
    given_name = models.CharField(_("given name"), max_length=100)
    family_name = models.CharField(_("family name"), max_length=100)
    address = models.CharField(
        _("address"), max_length=100, blank=True, help_text=_("Mr./Ms./...")
    )
    address_on_first_name_terms = models.BooleanField(
        _("address on first-name terms"), default=False
    )
    salutation = models.CharField(
        _("complete salutation"),
        max_length=100,
        help_text=_("Dear John/Dear Ms Smith"),
    )
    date_of_birth = models.DateField(_("date of birth"), blank=True, null=True)
    year_of_birth_unknown = models.BooleanField(
        _("year of birth unknown"),
        default=False,
        help_text=_("Only the day and the month of the date of birth are known."),
    )
    notes = models.TextField(_("notes"), blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("organization"),
        related_name="people",
    )
    primary_contact = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("primary contact"),
    )
    groups = models.ManyToManyField(Group, verbose_name=_("groups"), blank=True)
    _fts = models.TextField(editable=False, blank=True)

    objects = PersonQuerySet.as_manager()

    class Meta:
        ordering = ["given_name", "family_name"]
        verbose_name = _("person")
        verbose_name_plural = _("people")

    def __str__(self):
        parts = [self.full_name]
        if self.is_archived:
            parts.append(gettext("(archived)"))
        return " ".join(parts)

    @property
    def birthday(self):
        """The date of birth formatted without the year if it isn't known"""
        return local_date_format(
            self.date_of_birth, fmt="d.m." if self.year_of_birth_unknown else None
        )

    @property
    def full_name(self):
        return " ".join(filter(None, (self.given_name, self.family_name)))

    def all_groups(self):
        """The person's groups and those of their organization which apply to
        organizations"""
        groups = {group.pk: group for group in self.groups.all()}
        if self.organization:
            groups |= {
                group.pk: group
                for group in self.organization.groups.all()
                if group.applies_to_organizations
            }
        return sorted(groups.values(), key=lambda group: group.title.lower())

    def add_to_group(self, group):
        """Groups which apply to organizations go to the organization, like in
        the person form; only people without organization are members
        themselves"""
        if group.applies_to_organizations and self.organization:
            self.organization.groups.add(group)
        else:
            self.groups.add(group)

    def remove_from_group(self, group):
        """Also removes groups which apply to organizations from the
        organization, like unchecking them in the person form"""
        self.groups.remove(group)
        if group.applies_to_organizations and self.organization:
            self.organization.groups.remove(group)

    @property
    def name_with_organization(self):
        if self.organization and not self.organization.is_private_person:
            return f"{self.organization} / {self.full_name}"
        return self.full_name

    @classmethod
    def allow_delete(cls, instance, request):
        return None

    def recent_projects(self):
        return self.project_set.select_related("owned_by")[:10]

    def possible_duplicates(self):
        from workbench.contacts.merge import duplicates_of

        return duplicates_of(self)

    def recent_deals(self):
        return self.deal_set.select_related("owned_by").order_by("-pk")[:10]

    def recent_invoices(self):
        return self.invoice_set.select_related("owned_by")[:10]

    def fts_text(self):
        return " ".join(
            itertools.chain(
                [self.organization.name if self.organization else ""],
                (detail.phone_number for detail in self.phonenumbers.all()),
                (detail.email for detail in self.emailaddresses.all()),
                (detail.postal_address for detail in self.postaladdresses.all()),
            )
        )

    def refresh_related_fts(self):
        """The search texts of related objects contain the name"""
        from workbench.deals.models import Deal
        from workbench.invoices.models import Invoice
        from workbench.offers.models import Offer
        from workbench.projects.models import Project

        refresh_fts(Project.objects.filter(contact=self))
        refresh_fts(Offer.objects.filter(project__contact=self))
        refresh_fts(Deal.objects.filter(contact=self))
        refresh_fts(Invoice.objects.filter(contact=self))

    def save(self, *args, **kwargs):
        renamed = (
            self.pk
            and Person.objects
            .filter(pk=self.pk)
            .exclude(given_name=self.given_name, family_name=self.family_name)
            .exists()
        )
        if self.pk:
            self._fts = self.fts_text()
        super().save(*args, **kwargs)
        if renamed:
            self.refresh_related_fts()

    save.alters_data = True


def update_organization_archival(person):
    """Archive the organization with its last active person, unless it has
    open projects or deals (someone will add a new contact), and unarchive
    it with one of its people. Returns the organization if it changed."""
    from workbench.deals.models import Deal
    from workbench.projects.models import Project

    organization = person.organization
    if not organization:
        return None
    if person.is_archived:
        if (
            organization.is_archived
            or organization.people.active().exists()
            or Project.objects.open().filter(customer=organization).exists()
            or Deal.objects.filter(customer=organization, status=Deal.OPEN).exists()
        ):
            return None
        organization.is_archived = True
    elif organization.is_archived:
        organization.is_archived = False
    else:
        return None
    organization.save()
    return organization


_home_re = re.compile(r"(home|hause|privat)", re.IGNORECASE)


class PersonDetail(Model):
    WEIGHTS = (
        (re.compile(r"mobil", re.IGNORECASE), 30),
        (re.compile(r"(work|arbeit)", re.IGNORECASE), 20),
        (_home_re, 10),
        (re.compile(r"(organization|firm)", re.IGNORECASE), -100),
    )

    type = models.CharField(_("type"), max_length=40, default=_("work"))
    weight = models.SmallIntegerField(_("weight"), default=0, editable=False)

    class Meta:
        abstract = True

    @property
    def urls(self):
        return self.person.urls

    def get_absolute_url(self):
        return self.person.urls["detail"]

    def save(self, *args, **kwargs):
        self.weight = sum(
            (weight for regex, weight in self.WEIGHTS if regex.search(str(self.type))),
            0,
        )
        super().save(*args, **kwargs)

    save.alters_data = True


class PhoneNumber(PersonDetail):
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        verbose_name=_("person"),
        related_name="phonenumbers",
    )
    phone_number = models.CharField(_("phone number"), max_length=100)

    class Meta:
        ordering = ("-weight", "id")
        verbose_name = _("phone number")
        verbose_name_plural = _("phone numbers")

    def __str__(self):
        return self.phone_number

    def clean_fields(self, exclude):
        super().clean_fields(exclude)
        errors = {}
        try:
            number = phonenumbers.parse(self.phone_number, "CH")
        except phonenumbers.NumberParseException as exc:
            errors["phone_number"] = str(exc)
        else:
            if phonenumbers.is_valid_number(number):
                self.phone_number = phonenumbers.format_number(
                    number, phonenumbers.PhoneNumberFormat.E164
                )
            else:
                errors["phone_number"] = _("Phone number invalid.")
        raise_if_errors(errors, exclude)

    @property
    def pretty_number(self):
        try:
            return phonenumbers.format_number(
                phonenumbers.parse(self.phone_number),
                phonenumbers.PhoneNumberFormat.INTERNATIONAL,
            )
        except Exception:  # noqa: BLE001
            return self.phone_number


class EmailAddress(PersonDetail):
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        verbose_name=_("person"),
        related_name="emailaddresses",
    )
    email = models.EmailField(_("email"), max_length=254)

    class Meta:
        ordering = ("-weight", "id")
        verbose_name = _("email address")
        verbose_name_plural = _("email addresses")

    def __str__(self):
        return self.email


class PostalAddress(PersonDetail):
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        verbose_name=_("person"),
        related_name="postaladdresses",
    )
    street = models.CharField(_("street"), max_length=100)
    house_number = models.CharField(_("house number"), max_length=20, blank=True)
    address_suffix = models.CharField(_("address suffix"), max_length=100, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=20)
    city = models.CharField(_("city"), max_length=100)
    country = CountryField(_("country"), default="CH")
    postal_address_override = models.TextField(
        _("override"),
        blank=True,
        help_text=_("Completely overrides the postal address if set."),
    )

    class Meta:
        ordering = ("-weight", "id")
        verbose_name = _("postal address")
        verbose_name_plural = _("postal addresses")

    def __str__(self):
        return self.postal_address

    @property
    def postal_address(self):
        if self.postal_address_override:
            return self.postal_address_override
        lines = [
            self.person.organization.name
            if self.person.organization
            and not self.person.organization.is_private_person
            and not _home_re.search(self.type)
            else "",
            self.person.full_name,
            " ".join(filter(None, (self.street, self.house_number))),
            self.address_suffix,
            " ".join(filter(None, (self.postal_code, self.city))),
            self.country.name if self.country.code != "CH" else "",
        ]
        return "\n".join(filter(None, lines))

    def get_maps_url(self):
        parts = [self.street, self.house_number, self.postal_code, self.city]
        if any(parts):
            return "https://www.google.com/maps?{}".format(
                urlencode({"q": " ".join(parts)})
            )
        return None


ADDRESS_FIELDS = (
    "street",
    "house_number",
    "address_suffix",
    "postal_code",
    "city",
    "country",
    "postal_address_override",
)


def organization_postal_addresses(organization, *, exclude_person=None):
    """Distinct postal addresses of the organization's active people, those
    of most people first, without those ``exclude_person`` has already

    Returns dicts with the ``fields`` of ``ADDRESS_FIELDS``, the ``type``,
    the address on one ``line``, the ``people`` who have it (and their
    ``names``) and their ``addresses``."""
    addresses = {}
    for address in (
        PostalAddress.objects
        .filter(person__organization=organization, person__is_archived=False)
        .select_related("person")
        .order_by("person__given_name", "person__family_name", "-weight", "pk")
    ):
        fields = {
            field: str(getattr(address, field)).strip() for field in ADDRESS_FIELDS
        }
        entry = addresses.setdefault(
            tuple(value.casefold() for value in fields.values()),
            {
                "fields": fields,
                "type": address.type,
                "line": ", ".join(
                    line.strip()
                    for line in address.postal_address_override.splitlines()
                    if line.strip()
                )
                or ", ".join(
                    filter(
                        None,
                        (
                            " ".join(
                                filter(None, (address.street, address.house_number))
                            ),
                            address.address_suffix,
                            " ".join(filter(None, (address.postal_code, address.city))),
                            address.country.name
                            if address.country.code != "CH"
                            else "",
                        ),
                    )
                ),
                "people": [],
                "addresses": [],
            },
        )
        entry["addresses"].append(address)
        if address.person not in entry["people"]:
            entry["people"].append(address.person)
    if exclude_person:
        for key, entry in list(addresses.items()):
            if exclude_person in entry["people"]:
                del addresses[key]
    for entry in addresses.values():
        entry["names"] = ", ".join(person.full_name for person in entry["people"])
    return sorted(addresses.values(), key=lambda entry: -len(entry["people"]))


def postal_address_choices(*, organization=None, person=None, for_billing=False):
    """Postal addresses of the person, or of the organization's people

    Returns a list of ``(type, postal_address)`` tuples."""
    postal_addresses = []

    if person:
        if (
            for_billing
            and person.organization
            and person.organization.default_billing_address
        ):
            postal_addresses.append((
                _("default billing address"),
                person.organization.default_billing_address,
            ))
        postal_addresses.extend(
            (pa.type, pa.postal_address)
            for pa in PostalAddress.objects.filter(person=person).select_related(
                "person__organization"
            )
        )

    if organization and (not person or not postal_addresses):
        if for_billing and organization.default_billing_address:
            postal_addresses.append((
                _("default billing address"),
                organization.default_billing_address,
            ))
        postal_addresses.extend(
            (pa.type, pa.postal_address)
            for pa in PostalAddress.objects
            .filter(person__organization=organization)
            .exclude(person=person)
            .exclude(person__is_archived=True)
            .select_related("person__organization")
        )

    return postal_addresses
