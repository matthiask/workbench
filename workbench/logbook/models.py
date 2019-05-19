from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.projects.models import Project, Service
from workbench.tools.models import HoursField, Model, MoneyField
from workbench.tools.urls import model_urls
from workbench.tools.validation import monday


@model_urls
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
    hours = HoursField(_("hours"), validators=[MinValueValidator(Decimal("0.1"))])
    description = models.TextField(_("description"))

    invoice_service = models.ForeignKey(
        "invoices.Service",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("invoice service"),
        related_name="+",
    )
    archived_at = models.DateTimeField(_("archived at"), blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["-rendered_on"])]
        ordering = ("-rendered_on", "-created_at")
        verbose_name = _("logged hours")
        verbose_name_plural = _("logged hours")

    def __str__(self):
        return "%s: %s" % (self.service.title, self.description)

    def __html__(self):
        return format_html("{}:<br>{}", self.service.title, self.description)

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.invoice_service_id or instance.archived_at:
            messages.error(request, _("Cannot delete archived logged hours."))
            return False
        if instance.rendered_on < monday():
            messages.error(request, _("Cannot delete logged hours from past weeks."))
            return False
        return super().allow_delete(instance, request)

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return cls().urls["list"] + "?project={}".format(
                instance.service.project_id if instance else ""
            )


@model_urls
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
    rendered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="loggedcosts",
        verbose_name=_("rendered by"),
    )
    cost = MoneyField(_("cost"))
    third_party_costs = MoneyField(
        _("third party costs"),
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )
    description = models.TextField(_("description"))

    invoice_service = models.ForeignKey(
        "invoices.Service",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("invoice service"),
        related_name="+",
    )
    archived_at = models.DateTimeField(_("archived at"), blank=True, null=True)

    are_expenses = models.BooleanField(_("are expenses"), default=False)
    expenses_reimbursed_at = models.DateTimeField(
        _("expenses reimbursed at"), blank=True, null=True
    )

    class Meta:
        ordering = ("-rendered_on", "-created_at")
        verbose_name = _("logged cost")
        verbose_name_plural = _("logged costs")

    def __str__(self):
        return self.description

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.invoice_service_id or instance.archived_at:
            messages.error(request, _("Cannot delete archived logged cost entries."))
            return False
        if instance.expenses_reimbursed_at:
            messages.error(
                request,
                _("Expenses have already been reimbursed, cannot delete entry."),
            )
        return super().allow_delete(instance, request)

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return cls().urls["list"] + "?project={}".format(
                instance.project_id if instance else ""
            )
