from datetime import date, timedelta

from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.projects.models import Project, Service
from workbench.tools.models import SearchManager, Model, MoneyField, HoursField
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


@model_urls()
class LoggedHours(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="loggedhours",
        verbose_name=_("service"),
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="+", verbose_name=_("created by")
    )
    rendered_on = models.DateField(_("rendered on"), default=date.today)
    rendered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="loggedhours",
        verbose_name=_("rendered by"),
    )
    hours = HoursField(_("hours"))
    description = models.TextField(_("description"))

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("invoice"),
        related_name="+",
    )
    archived_at = models.DateTimeField(_("archived at"), blank=True, null=True)

    objects = SearchManager()

    class Meta:
        indexes = [models.Index(fields=["-rendered_on"])]
        ordering = ("-rendered_on", "-created_at")
        verbose_name = _("logged hours")
        verbose_name_plural = _("logged hours")

    def __str__(self):
        return "%s: %s" % (self.service.title, self.description)

    def __html__(self):
        return format_html("{}:<br>{}", self.service.title, self.description)

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude)
        errors = {}
        today = date.today()
        if self.rendered_on > today + timedelta(days=7):
            errors["rendered_on"] = _("Sorry, too early.")
        raise_if_errors(errors, exclude or ())


@model_urls()
class LoggedCost(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="loggedcosts",
        verbose_name=_("project"),
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="loggedcosts",
        verbose_name=_("service"),
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="+", verbose_name=_("created by")
    )
    rendered_on = models.DateField(_("rendered on"), default=date.today)
    cost = MoneyField(_("cost"), default=None)
    third_party_costs = MoneyField(
        _("third party costs"),
        default=None,
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )
    description = models.TextField(_("description"))

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("invoice"),
        related_name="+",
    )
    archived_at = models.DateTimeField(_("archived at"), blank=True, null=True)

    objects = SearchManager()

    class Meta:
        ordering = ("-rendered_on", "-created_at")
        verbose_name = _("logged cost")
        verbose_name_plural = _("logged costs")

    def __str__(self):
        return self.description
