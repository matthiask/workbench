from datetime import date, timedelta

from django.contrib import messages
from django.db import models
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.models import Model, HoursField
from workbench.tools.urls import model_urls


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
    january = models.DecimalField(_("january"), max_digits=4, decimal_places=2)
    february = models.DecimalField(_("february"), max_digits=4, decimal_places=2)
    march = models.DecimalField(_("march"), max_digits=4, decimal_places=2)
    april = models.DecimalField(_("april"), max_digits=4, decimal_places=2)
    may = models.DecimalField(_("may"), max_digits=4, decimal_places=2)
    june = models.DecimalField(_("june"), max_digits=4, decimal_places=2)
    july = models.DecimalField(_("july"), max_digits=4, decimal_places=2)
    august = models.DecimalField(_("august"), max_digits=4, decimal_places=2)
    september = models.DecimalField(_("september"), max_digits=4, decimal_places=2)
    october = models.DecimalField(_("october"), max_digits=4, decimal_places=2)
    november = models.DecimalField(_("november"), max_digits=4, decimal_places=2)
    december = models.DecimalField(_("december"), max_digits=4, decimal_places=2)
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


class Employment(Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="employments",
    )
    date_from = models.DateField(_("date from"), default=date.today)
    date_until = models.DateField(_("date until"), default=date.max)
    percentage = models.IntegerField(_("percentage"))
    vacation_days = models.DecimalField(
        _("vacation days"),
        max_digits=4,
        decimal_places=2,
        help_text=_("Vacation days if percentage was active for a full year."),
    )
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        ordering = ["date_from"]
        unique_together = ["user", "date_from"]
        verbose_name = _("employment")
        verbose_name_plural = _("employments")

    def __str__(self):
        return "%s - %s" % (self.date_from, self.date_until or _("ongoing"))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        next = None
        for employment in self.user.employments.reverse():
            if next is None:
                next = employment
            else:
                if employment.date_until >= next.date_from:
                    employment.date_until = next.date_from - timedelta(days=1)
                    super(Employment, employment).save()
                next = employment

    save.alters_data = True


@model_urls()
class Absence(Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_("user"), related_name="absences"
    )
    starts_on = models.DateField(_("starts on"))
    days = models.DecimalField(_("days"), max_digits=4, decimal_places=2)
    description = models.TextField(_("description"))
    is_vacation = models.BooleanField(_("is vacation"), default=True)

    class Meta:
        ordering = ["-starts_on", "-pk"]
        verbose_name = _("absence")
        verbose_name_plural = _("absences")

    def __str__(self):
        return self.description

    @classmethod
    def allow_update(cls, instance, request):
        if instance.starts_on.year < date.today().year:
            messages.error(request, _("Absences of past years are locked."))
            return False
        return True

    allow_delete = allow_update
