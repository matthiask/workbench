from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.invoices.models import Invoice
from workbench.tools.formats import local_date_format
from workbench.tools.models import Model, MoneyField, SearchQuerySet
from workbench.tools.urls import model_urls


class AccountStatementQuerySet(SearchQuerySet):
    pass


@model_urls()
class AccountStatement(Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="+", verbose_name=_("created by")
    )
    processed_at = models.DateTimeField(_("processed at"), blank=True, null=True)
    statement = models.BinaryField(_("statement"))
    title = models.CharField(_("title"), max_length=200, blank=True)

    objects = AccountStatementQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("account statement")
        verbose_name_plural = _("account statements")

    def __str__(self):
        return self.title

    def context(self):
        return [c for c in [self.contact, self.deal, self.project] if c]

    def pretty_status(self):
        if self.processed_at:
            return local_date_format(self.processed_at, "d.m.Y")

        return _("open")


@model_urls()
class CreditEntry(models.Model):
    account_statement = models.ForeignKey(
        AccountStatement,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
        verbose_name=_("account statement"),
    )
    reference_number = models.CharField(
        _("reference number"), max_length=40, unique=True
    )
    value_date = models.DateField(_("value date"))
    total = MoneyField(_("total"))
    payment_notice = models.CharField(_("payment notice"), max_length=1000, blank=True)

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="+",
        verbose_name=_("invoice"),
    )
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        ordering = ["value_date", "pk"]
        verbose_name = _("credit entry")
        verbose_name_plural = _("credit entries")

    def __str__(self):
        return self.reference_number
