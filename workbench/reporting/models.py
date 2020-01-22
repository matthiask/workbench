from django.db import models
from django.utils.translation import gettext_lazy as _

from workbench.projects.models import Project
from workbench.tools.formats import currency, local_date_format
from workbench.tools.models import Model, MoneyField
from workbench.tools.validation import is_end_of_month


class MonthlyAccrualQuerySet(models.QuerySet):
    def accruals(self, cutoff_date):
        from workbench.reporting.project_budget_statistics import (
            project_budget_statistics,
        )

        projects = Project.objects.open(on=cutoff_date)
        statistics = project_budget_statistics(projects, cutoff_date=cutoff_date)
        return statistics["overall"]["delta_negative"]

    def for_cutoff_date(self, cutoff_date):
        instance, created = self.update_or_create(
            cutoff_date=cutoff_date, defaults={"accruals": self.accruals(cutoff_date)},
        )
        return instance


class MonthlyAccrual(models.Model):
    cutoff_date = models.DateField(_("cutoff date"), unique=True)
    accruals = MoneyField(_("accruals"))
    not_yet_invoiced = MoneyField(_("not yet invoiced"))

    objects = MonthlyAccrualQuerySet.as_manager()

    class Meta:
        ordering = ["-cutoff_date"]
        verbose_name = _("monthly accruals")
        verbose_name_plural = _("monthly accruals")

    def __str__(self):
        return local_date_format(self.cutoff_date)


class Accrual(Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, verbose_name=_("project"), related_name="+",
    )
    cutoff_date = models.DateField(_("cutoff date"))
    accrual = MoneyField(
        _("accrual"),
        help_text=_(
            "Positive values for not yet invoiced services,"
            " negative values for accruals."
        ),
    )
    justification = models.TextField(_("justification"))

    class Meta:
        unique_together = [("project", "cutoff_date")]
        verbose_name = _("accrual")
        verbose_name_plural = _("accruals")

    def __str__(self):
        return currency(self.accrual, plus_sign=True)

    def save(self, *args, **kwargs):
        assert is_end_of_month(self.cutoff_date)
        super().save(*args, **kwargs)

        MonthlyAccrual.objects.for_cutoff_date(self.cutoff_date)  # Regenerate

    save.alters_data = True
