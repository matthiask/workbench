from django.db import models
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from tools.models import SearchManager
from tools.urls import model_urls


@model_urls()
class Group(models.Model):
    title = models.CharField(_('title'), max_length=100)

    class Meta:
        verbose_name = _('group')
        verbose_name_plural = _('groups')

    def __str__(self):
        return self.title


@model_urls()
class Organization(models.Model):
    name = models.TextField(_('name'))
    primary_contact = models.ForeignKey(
        User,
        verbose_name=_('primary contact'),
        related_name='+')

    objects = SearchManager()

    class Meta:
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')

    def __str__(self):
        return self.name


@model_urls()
class Person(models.Model):
    full_name = models.CharField(_('full name'), max_length=100)
    address = models.CharField(
        _('address'),
        max_length=100,
        blank=True,
        help_text=_('E.g. Dear John.'))
    notes = models.TextField(_('notes'), blank=True)
    organization = models.ForeignKey(
        Organization,
        verbose_name=_('organization'),
        related_name='people')
    primary_contact = models.ForeignKey(
        User,
        verbose_name=_('primary contact'),
        related_name='+')

    objects = SearchManager()

    class Meta:
        verbose_name = _('person')
        verbose_name_plural = _('people')

    def __str__(self):
        return self.full_name


class PhoneNumber(models.Model):
    person = models.ForeignKey(
        Person,
        verbose_name=_('person'),
        related_name='phonenumbers')
    type = models.CharField(_('type'), max_length=40)
    phone_number = models.CharField(_('phone number'), max_length=100)

    class Meta:
        verbose_name = _('phone number')
        verbose_name_plural = _('phone numbers')

    def __str__(self):
        return self.phone_number

    def get_absolute_url(self):
        return self.person.urls.url('detail')

    @property
    def urls(self):
        return self.person.urls


class EmailAddress(models.Model):
    person = models.ForeignKey(
        Person,
        verbose_name=_('person'),
        related_name='emailaddresses')
    type = models.CharField(_('type'), max_length=40)
    email = models.EmailField(_('email'), max_length=254)

    class Meta:
        verbose_name = _('email address')
        verbose_name_plural = _('email addresses')

    def __str__(self):
        return self.email

    def get_absolute_url(self):
        return self.person.urls.url('detail')

    @property
    def urls(self):
        return self.person.urls


class PostalAddress(models.Model):
    person = models.ForeignKey(
        Person,
        verbose_name=_('person'),
        related_name='postaladdresses')
    type = models.CharField(_('type'), max_length=40)
    postal_address = models.TextField(_('postal address'))

    class Meta:
        verbose_name = _('postal address')
        verbose_name_plural = _('postal addresses')

    def __str__(self):
        return self.postal_address

    def get_absolute_url(self):
        return self.person.urls.url('detail')

    @property
    def urls(self):
        return self.person.urls
