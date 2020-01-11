from django.db import models
from django.utils.translation import gettext_lazy as _

from workbench.tools.formats import local_date_format
from workbench.tools.models import MoneyField


class Accruals(models.Model):
    cutoff_date = models.DateField(_("cutoff date"), unique=True)
    accruals = MoneyField(_("accruals"))

    class Meta:
        ordering = ["-cutoff_date"]
        verbose_name = _("accruals")
        verbose_name_plural = _("accruals")

    def __str__(self):
        return local_date_format(self.cutoff_date)
