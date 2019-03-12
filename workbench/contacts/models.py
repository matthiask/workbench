import re

from django.db import models
from django.utils.translation import gettext_lazy as _

from django_countries.fields import CountryField

from workbench.accounts.models import User
from workbench.tools.models import SearchManager, Model
from workbench.tools.urls import model_urls


@model_urls()
class Group(Model):
    title = models.CharField(_("title"), max_length=100)

    class Meta:
        ordering = ("title",)
        verbose_name = _("group")
        verbose_name_plural = _("groups")

    def __str__(self):
        return self.title


@model_urls()
class Organization(Model):
    name = models.TextField(_("name"))
    notes = models.TextField(_("notes"), blank=True)
    primary_contact = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("primary contact"),
        related_name="+",
    )
    groups = models.ManyToManyField(
        Group, verbose_name=_("groups"), related_name="+", blank=True
    )

    objects = SearchManager()

    class Meta:
        ordering = ("name",)
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

    def __str__(self):
        return self.name


@model_urls()
class Person(Model):
    given_name = models.CharField(_("given name"), max_length=100)
    family_name = models.CharField(_("family name"), max_length=100)
    address = models.CharField(
        _("address"), max_length=100, blank=True, help_text=_("Mr./Ms.")
    )
    salutation = models.CharField(
        _("salutation"),
        max_length=100,
        blank=True,
        help_text=_("Dear John/Dear Ms Smith"),
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
        verbose_name=_("primary contact"),
        related_name="+",
    )
    groups = models.ManyToManyField(
        Group, verbose_name=_("groups"), related_name="+", blank=True
    )

    objects = SearchManager()

    class Meta:
        ordering = ["given_name", "family_name"]
        verbose_name = _("person")
        verbose_name_plural = _("people")

    def __str__(self):
        if self.organization_id:
            return "%s / %s" % (self.full_name, self.organization)
        return self.full_name

    @property
    def full_name(self):
        return " ".join(filter(None, (self.given_name, self.family_name)))


class PersonDetail(Model):
    WEIGHTS = (
        (re.compile(r"mobile", re.I), 30),
        (re.compile(r"work", re.I), 20),
        (re.compile(r"home", re.I), 10),
        (re.compile(r"organization", re.I), -100),
    )

    type = models.CharField(_("type"), max_length=40)
    weight = models.SmallIntegerField(_("weight"), default=0, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.weight = sum(
            (weight for regex, weight in self.WEIGHTS if regex.search(self.type)), 0
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

    def get_absolute_url(self):
        return self.person.urls.url("detail")

    @property
    def urls(self):
        return self.person.urls


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

    def get_absolute_url(self):
        return self.person.urls.url("detail")

    @property
    def urls(self):
        return self.person.urls


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

    def get_absolute_url(self):
        return self.person.urls.url("detail")

    @property
    def urls(self):
        return self.person.urls

    @property
    def postal_address(self):
        if self.postal_address_override:
            return self.postal_address_override
        lines = [
            self.person.organization.name if self.person.organization else "",
            self.person.full_name,
            " ".join(filter(None, (self.street, self.house_number))),
            self.address_suffix,
            " ".join(filter(None, (self.postal_code, self.city))),
            self.country.name if self.country.code != "CH" else "",
        ]
        return "\n".join(filter(None, lines))
