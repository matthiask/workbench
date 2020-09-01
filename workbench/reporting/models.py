from django.db import models
from django.utils.translation import gettext_lazy as _

from workbench.projects.models import Project
from workbench.reporting.project_budget_statistics import project_budget_statistics
from workbench.tools.formats import local_date_format
from workbench.tools.models import MoneyField


class AccrualsQuerySet(models.QuerySet):
    def accruals(self, cutoff_date):
        projects = Project.objects.open(on=cutoff_date)
        statistics = project_budget_statistics(projects, cutoff_date=cutoff_date)
        return statistics["overall"]["delta_negative"]

    def for_cutoff_date(self, cutoff_date):
        instance, created = self.update_or_create(
            cutoff_date=cutoff_date,
            defaults={"accruals": self.accruals(cutoff_date)},
        )
        return instance


class Accruals(models.Model):
    cutoff_date = models.DateField(_("cutoff date"), unique=True)
    accruals = MoneyField(_("accruals"))

    objects = AccrualsQuerySet.as_manager()

    class Meta:
        ordering = ["-cutoff_date"]
        verbose_name = _("accruals")
        verbose_name_plural = _("accruals")

    def __str__(self):
        return local_date_format(self.cutoff_date)


class CostCenter(models.Model):
    title = models.CharField(_("title"), max_length=200)
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("cost center")
        verbose_name_plural = _("cost centers")

    def __str__(self):
        return self.title
