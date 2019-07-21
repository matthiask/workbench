from django.contrib import messages
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.formats import local_date_format
from workbench.tools.models import Model, MoneyField, Z
from workbench.tools.urls import model_urls


@model_urls
class ExpenseReport(Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="+", verbose_name=_("created by")
    )
    closed_on = models.DateField(_("closed on"), blank=True, null=True)
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="expensereports",
        verbose_name=_("responsible"),
    )
    total = MoneyField(
        _("total"),
        default=Z,
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("expense report")
        verbose_name_plural = _("expense reports")

    def __str__(self):
        return "%s: %s %s" % (
            self._meta.verbose_name,
            self.owned_by.get_full_name(),
            local_date_format(self.created_at),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            self.total = self.expenses.aggregate(t=Sum("third_party_costs"))["t"] or Z
        super().save(*args, **kwargs)

    save.alters_data = True

    def delete(self, *args, **kwargs):
        self.expenses.update(expense_report=None)
        super().delete(*args, **kwargs)

    delete.alters_data = True

    @classmethod
    def allow_update(cls, instance, request):
        if instance.closed_on:
            messages.error(request, _("Cannot update a closed expense report."))
        return not instance.closed_on

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.closed_on:
            messages.error(request, _("Cannot delete a closed expense report."))
        return not instance.closed_on

    @property
    def status_css(self):
        return "light" if self.closed_on else "info"

    @property
    def pretty_status(self):
        return (
            (_("closed on %s") % local_date_format(self.closed_on))
            if self.closed_on
            else _("In preparation")
        )
