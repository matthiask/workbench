import datetime as dt

from django.contrib import messages
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.expenses.rates import exchange_rates
from workbench.logbook.models import LoggedCost
from workbench.tools.formats import Z2, currency, local_date_format
from workbench.tools.models import Model, MoneyField
from workbench.tools.urls import model_urls


@model_urls
class ExpenseReport(Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("created by")
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
        default=Z2,
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("expense report")
        verbose_name_plural = _("expense reports")

    def __str__(self):
        return "%s, %s, %s" % (
            self.owned_by.get_full_name(),
            local_date_format(self.created_at.date()),
            currency(self.total),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            self.total = self.expenses.aggregate(t=Sum("third_party_costs"))["t"] or Z2
        super().save(*args, **kwargs)

    save.alters_data = True

    def delete(self, *args, **kwargs):
        self.expenses.update(expense_report=None)
        super().delete(*args, **kwargs)

    delete.alters_data = True

    @classmethod
    def allow_create(cls, request):
        if (
            LoggedCost.objects.expenses(user=request.user)
            .filter(expense_report__isnull=True)
            .exists()
        ):
            return True
        messages.error(request, _("Could not find any expenses to reimburse."))
        return False

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
    def pretty_status(self):
        return (
            (_("closed on %s") % local_date_format(self.closed_on))
            if self.closed_on
            else _("In preparation")
        )

    @property
    def status_badge(self):
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            "light" if self.closed_on else "info",
            self.pretty_status,
        )


class ExchangeRatesQuerySet(models.QuerySet):
    def for_day(self, day):
        try:
            return self.get(day=day)
        except self.model.DoesNotExist:
            instance, created = self.update_or_create(
                day=day, defaults={"rates": exchange_rates(day)}
            )
            return instance

    def newest(self):
        try:
            return self.latest()
        except self.model.DoesNotExist:
            return self.for_day(dt.date.today())


class ExchangeRates(models.Model):
    day = models.DateField(_("day"), unique=True)
    rates = models.JSONField()

    objects = ExchangeRatesQuerySet.as_manager()

    class Meta:
        get_latest_by = "day"
        ordering = ["-day"]
        verbose_name = _("exchange rate")
        verbose_name_plural = _("exchange rates")

    def __str__(self):
        return str(self.day)
