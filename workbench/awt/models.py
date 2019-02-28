from django.db import models
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.models import Model, HoursField


class Year(Model):
    MONTHS = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]

    year = models.IntegerField(_("year"), unique=True)
    january = models.DecimalField(_("january"), max_digits=5, decimal_places=2)
    february = models.DecimalField(_("february"), max_digits=5, decimal_places=2)
    march = models.DecimalField(_("march"), max_digits=5, decimal_places=2)
    april = models.DecimalField(_("april"), max_digits=5, decimal_places=2)
    may = models.DecimalField(_("may"), max_digits=5, decimal_places=2)
    june = models.DecimalField(_("june"), max_digits=5, decimal_places=2)
    july = models.DecimalField(_("july"), max_digits=5, decimal_places=2)
    august = models.DecimalField(_("august"), max_digits=5, decimal_places=2)
    september = models.DecimalField(_("september"), max_digits=5, decimal_places=2)
    october = models.DecimalField(_("october"), max_digits=5, decimal_places=2)
    november = models.DecimalField(_("november"), max_digits=5, decimal_places=2)
    december = models.DecimalField(_("december"), max_digits=5, decimal_places=2)
    working_time_per_day = HoursField(_("working time per day"))

    class Meta:
        ordering = ["-year"]
        verbose_name = _("year")
        verbose_name_plural = _("years")

    def __str__(self):
        return self.year

    @property
    def days(self):
        return sum(getattr(self, field) for field in self.MONTHS)


class Quota(Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="quotas",
    )
    date_from = models.DateField(_("date from"))
    date_until = models.DateField(_("date until"), blank=True, null=True)
    percentage = models.IntegerField(_("percentage"))
    vacation_days = models.DecimalField(_("vacation days"), help_text=_("Vacation days if percentage was active for a full year."))

    class Meta:
        ordering = ["date_from"]
        verbose_name = _("quota")
        verbose_name_plural = _("quotas")

    def __str__(self):
        return "%s - %s" % (self.date_from, self.date_until or _("ongoing"))


class Break(Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="breaks",
    )
    starts_on = models.DateField(_("starts_on"))
    hours = HoursField(_("hours"))
    description = models.TextField(_("description"))
    is_vacation = models.BooleanField(_("is vacation"), default=True)

    class Meta:
        ordering = ["-month", "-pk"]
        verbose_name = _("break")
        verbose_name_plural = _("breaks")

    def __str__(self):
        return self.title
