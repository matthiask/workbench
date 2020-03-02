from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.tools.formats import currency, local_date_format
from workbench.tools.models import Model, MoneyField, Z
from workbench.tools.urls import model_urls


class NotArchivedQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)


class AttributeGroup(models.Model):
    title = models.CharField(_("title"), max_length=200)
    position = models.PositiveIntegerField(_("position"), default=0)
    is_archived = models.BooleanField(_("is archived"), default=False)
    is_required = models.BooleanField(_("is required"), default=True)

    objects = NotArchivedQuerySet.as_manager()

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("attribute group")
        verbose_name_plural = _("attribute groups")

    def __str__(self):
        return self.title


class Attribute(models.Model):
    group = models.ForeignKey(
        AttributeGroup,
        on_delete=models.CASCADE,
        related_name="attributes",
        verbose_name=_("attribute group"),
    )
    title = models.CharField(_("title"), max_length=200)
    position = models.PositiveIntegerField(_("position"), default=0)
    is_archived = models.BooleanField(_("is archived"), default=False)

    objects = NotArchivedQuerySet.as_manager()

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("attribute")
        verbose_name_plural = _("attributes")

    def __str__(self):
        return self.title


class ClosingType(models.Model):
    title = models.CharField(_("title"), max_length=200)
    represents_a_win = models.BooleanField(_("represents a win"), default=False)
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("closing type")
        verbose_name_plural = _("closing types")

    def __str__(self):
        return self.title


@model_urls
class Deal(Model):
    OPEN = 10
    ACCEPTED = 20
    DECLINED = 30

    STATUS_CHOICES = (
        (OPEN, _("open")),
        (ACCEPTED, _("accepted")),
        (DECLINED, _("declined")),
    )

    UNKNOWN = 10
    NORMAL = 20
    HIGH = 30

    PROBABILITY_CHOICES = [
        (UNKNOWN, _("unknown")),
        (NORMAL, _("normal")),
        (HIGH, _("high")),
    ]

    customer = models.ForeignKey(
        Organization, on_delete=models.PROTECT, verbose_name=_("customer")
    )
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("contact"),
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("responsible")
    )
    value = MoneyField(_("value"))

    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=OPEN
    )
    probability = models.IntegerField(
        _("probability"), choices=PROBABILITY_CHOICES, default=UNKNOWN
    )
    decision_expected_on = models.DateField(
        _("decision expected on"), blank=True, null=True
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)

    attributes = models.ManyToManyField(
        Attribute, verbose_name=_("attributes"), through="DealAttribute",
    )

    closed_on = models.DateField(_("closed on"), blank=True, null=True)
    closing_type = models.ForeignKey(
        ClosingType,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("closing type"),
    )
    closing_notice = models.TextField(_("closing notice"), blank=True)

    _fts = models.TextField(editable=False, blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = _("deal")
        verbose_name_plural = _("deals")

    def __str__(self):
        return "%s %s" % (self.title, self.owned_by.get_short_name())

    def __html__(self):
        return format_html(
            "<small>{}</small> {} - {}",
            self.code,
            self.title,
            self.owned_by.get_short_name(),
        )

    def save(self, *args, **kwargs):
        self.value = sum((v.value for v in self.values.all()), Z)
        super().save(*args, **kwargs)

    save.alters_data = True

    @property
    def pretty_status(self):
        d = {
            "created_at": local_date_format(self.created_at.date()),
            "closed_on": self.closed_on and local_date_format(self.closed_on),
            "status": self.get_status_display(),
        }

        if self.status == self.OPEN:
            return _("Open since %(created_at)s") % d
        return _("%(status)s on %(closed_on)s") % d

    @property
    def status_badge(self):
        css = {self.OPEN: "info", self.ACCEPTED: "success", self.DECLINED: "danger"}[
            self.status
        ]

        return format_html(
            '<span class="badge badge-{}">{}</span>', css, self.pretty_status
        )


class DealAttribute(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, verbose_name=_("deal"))
    attribute = models.ForeignKey(
        Attribute, on_delete=models.PROTECT, verbose_name=_("attribute")
    )

    class Meta:
        verbose_name = _("deal attribute")
        verbose_name_plural = _("deal attributes")

    def __str__(self):
        return "{} - {}".format(self.deal, self.attribute)


class ValueType(models.Model):
    title = models.CharField(_("title"), max_length=200)
    position = models.PositiveIntegerField(_("position"), default=0)
    is_archived = models.BooleanField(_("is archived"), default=False)

    objects = NotArchivedQuerySet.as_manager()

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("value type")
        verbose_name_plural = _("value types")

    def __str__(self):
        return self.title


class Value(models.Model):
    deal = models.ForeignKey(
        Deal, on_delete=models.CASCADE, related_name="values", verbose_name=_("deal")
    )
    type = models.ForeignKey(
        ValueType, on_delete=models.PROTECT, verbose_name=_("type")
    )
    value = MoneyField(_("value"))

    class Meta:
        ordering = ["type"]
        unique_together = [("deal", "type")]
        verbose_name = _("value")
        verbose_name_plural = _("values")

    def __str__(self):
        return currency(self.value)
