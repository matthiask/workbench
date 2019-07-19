from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.logbook.models import LoggedCost
from workbench.tools.formats import local_date_format
from workbench.tools.models import Model, MoneyField, Z
from workbench.tools.urls import model_urls


class ExpenseReportQuerySet(models.QuerySet):
    def create_report(self, *, user):
        expenses = self.expenses_for(user=user)
        if expenses.exists():
            report = self.create(created_by=user, owned_by=user)
            expenses.update(expense_report=report)
            report.save()
            return report
        return None

    def expenses_for(self, *, user):
        return LoggedCost.objects.filter(
            rendered_by=user, are_expenses=True, expense_report__isnull=True
        )


@model_urls
class ExpenseReport(Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="+", verbose_name=_("created by")
    )
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="expensereports",
        verbose_name=_("owned by"),
    )
    total = MoneyField(
        _("total"),
        default=Z,
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )

    objects = ExpenseReportQuerySet.as_manager()

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
