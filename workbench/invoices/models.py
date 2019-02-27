from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.projects.models import Project
from workbench.tools.formats import local_date_format
from workbench.tools.models import ModelWithTotal, SearchQuerySet, MoneyField
from workbench.tools.urls import model_urls


class InvoiceQuerySet(SearchQuerySet):
    pass


@model_urls()
class Invoice(ModelWithTotal):
    IN_PREPARATION = 10
    SENT = 20
    REMINDED = 30
    PAID = 40
    CANCELED = 50
    REPLACED = 60

    STATUS_CHOICES = (
        (IN_PREPARATION, _("In preparation")),
        (SENT, _("Sent")),
        (REMINDED, _("Reminded")),
        (PAID, _("Paid")),
        (CANCELED, _("Canceled")),
        (REPLACED, _("Replaced")),
    )

    FIXED = "fixed"
    DOWN_PAYMENT = "down-payment"
    SERVICES = "services"

    TYPE_CHOICES = (
        (FIXED, _("Fixed amount")),
        (DOWN_PAYMENT, _("Down payment")),
        (SERVICES, _("Services")),
    )

    customer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        verbose_name=_("customer"),
        related_name="+",
    )
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("contact"),
        related_name="+",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("project"),
        related_name="invoices",
    )

    invoiced_on = models.DateField(_("invoiced on"), blank=True, null=True)
    due_on = models.DateField(_("due on"), blank=True, null=True)
    closed_on = models.DateField(
        _("closed on"),
        blank=True,
        null=True,
        help_text=_(
            "Payment date for paid invoices, date of"
            " replacement or cancellation otherwise."
        ),
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("owned by"), related_name="+"
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=IN_PREPARATION
    )
    type = models.CharField(_("type"), max_length=20, choices=TYPE_CHOICES)
    down_payment_applied_to = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("down payment applied to"),
        related_name="down_payment_invoices",
    )
    down_payment_total = MoneyField(_("down payment total"))

    postal_address = models.TextField(_("postal address"), blank=True)
    _code = models.IntegerField(_("code"))

    payment_notice = models.TextField(_("payment notice"), blank=True)

    objects = models.Manager.from_queryset(InvoiceQuerySet)()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_status = self.status

    def __str__(self):
        return "%s %s" % (self.code, self.title)

    def __html__(self):
        return format_html("<small>{}</small> {}", self.code, self.title)

    def save(self, *args, **kwargs):
        new = False
        if not self.pk:
            self._code = RawSQL(
                "SELECT COALESCE(MAX(_code), 0) + 1 FROM invoices_invoice"
                " WHERE project_id = %s",
                (self.project_id,),
            )
            new = True
        super().save(*args, **kwargs)
        if new:
            self.refresh_from_db()

    save.alters_data = True

    @property
    def code(self):
        return (
            "%s-%04d" % (self.project.code, self._code)
            if self.project
            else "%05d" % self.pk
        )

    @property
    def total_excl_tax(self):
        return self.subtotal - self.discount - self.down_payment_total

    def clean(self):
        super().clean()

        if self.type == self.SERVICES:
            raise ValidationError({"type": _("Not implemented yet.")})

        if self.status >= self.SENT:
            if not self.invoiced_on or not self.due_on:
                raise ValidationError(
                    {"status": _("Invoice and/or due date missing for selected state.")}
                )

        if self.invoiced_on and self.due_on:
            if self.invoiced_on > self.due_on:
                raise ValidationError(
                    {"due_on": _("Due date has to be after invoice date.")}
                )

        if self.type in (self.SERVICES, self.DOWN_PAYMENT) and not self.project:
            raise ValidationError(
                {
                    _("Invoices of type %(type)s require a project.")
                    % {"type": self.get_type_display()}
                }
            )

    def pretty_status(self):
        d = {
            "invoiced_on": (
                local_date_format(self.invoiced_on, "d.m.Y")
                if self.invoiced_on
                else None
            ),
            "reminded_on": (
                local_date_format(self.invoiced_on, "d.m.Y")
                if self.invoiced_on
                else None
            ),
            "created_at": local_date_format(self.created_at, "d.m.Y"),
            "closed_on": (
                local_date_format(self.closed_on, "d.m.Y") if self.closed_on else None
            ),
        }

        if self.status == self.IN_PREPARATION:
            return _("In preparation since %(created_at)s") % d
        elif self.status == self.SENT:
            if self.due_on and date.today() > self.due_on:
                return _("Sent on %(invoiced_on)s, but overdue") % d

            return _("Sent on %(invoiced_on)s") % d
        elif self.status == self.REMINDED:
            return _("Sent on %(invoiced_on)s, reminded on %(reminded_on)s") % d
        elif self.status == self.PAID:
            return _("Paid on %(closed_on)s") % d
        else:
            return self.get_status_display()

    def status_css(self):
        if self.status == self.SENT:
            if self.due_on and date.today() > self.due_on:
                return "warning"

        return {
            self.IN_PREPARATION: "info",
            self.SENT: "success",
            self.REMINDED: "warning",
            self.PAID: "default",
            self.CANCELED: "danger",
            self.REPLACED: "",
        }[self.status]

    @property
    def total_title(self):
        if self.type == self.DOWN_PAYMENT:
            return (
                _("down payment total CHF incl. tax")
                if self.liable_to_vat
                else _("down payment total CHF")
            )
        else:
            return _("total CHF incl. tax") if self.liable_to_vat else _("total CHF")
