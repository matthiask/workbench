from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import models
from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.awt.utils import days_per_month, monthly_days
from workbench.logbook.models import LoggedHours
from workbench.tools.models import Model, HoursField
from workbench.tools.urls import model_urls


class YearQuerySet(models.QuerySet):
    def current(self):
        return self.filter(year=date.today().year).first()


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

    objects = YearQuerySet.as_manager()

    class Meta:
        ordering = ["-year"]
        verbose_name = _("year")
        verbose_name_plural = _("years")

    def __str__(self):
        return str(self.year)

    def get_absolute_url(self):
        return reverse("awt_year_detail", kwargs={"pk": self.pk})

    @property
    def months(self):
        return [getattr(self, field) for field in self.MONTHS]

    def statistics(self):
        from pprint import pprint

        users = User.objects.filter(is_active=True)
        user_dict = {u.id: u for u in users}
        target_hours = [self.working_time_per_day * days for days in self.months]

        months = defaultdict(
            lambda: [
                {
                    "percentage": 0,
                    "available_vacation_days": 0,
                    "vacation_days": 0,
                    "other_absences": 0,
                    "target": 0,
                    "hours": 0,
                }
                for i in range(12)
            ]
        )
        dpm = days_per_month(self.year)

        for employment in Employment.objects.filter(user__in=users).order_by(
            "-date_from"
        ):
            base_percentage = Decimal(employment.percentage)
            base_vacation_days = (
                Decimal(employment.vacation_weeks) * 5 / 12 * base_percentage / 100
            )
            for month, days in monthly_days(
                employment.date_from, employment.date_until
            ):
                if month.year < self.year:
                    continue
                elif month.year > self.year:
                    break
                record = months[user_dict[employment.user_id]][month.month - 1]
                factor = Decimal(days) / dpm[month.month - 1]
                record["target"] += target_hours[month.month - 1] * factor
                record["percentage"] += base_percentage * factor
                record["available_vacation_days"] += base_vacation_days * factor

        for row in (
            LoggedHours.objects.order_by()
            .filter(rendered_by__in=users, rendered_on__year=self.year)
            .values("rendered_by")
            .annotate(month=ExtractMonth("rendered_on"))
            .values("rendered_by", "month")
            .annotate(Sum("hours"))
        ):
            record = months[user_dict[row["rendered_by"]]][row["month"] - 1]
            record["hours"] += row["hours__sum"]

        for absence in Absence.objects.filter(
            user__in=users, starts_on__year=self.year
        ):
            record = months[user_dict[absence.user_id]][absence.starts_on.month - 1]
            record[
                "vacation_days" if absence.is_vacation else "other_absences"
            ] += absence.days

        pprint(dict(months))
        return months


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
    vacation_weeks = models.DecimalField(
        _("vacation weeks"),
        max_digits=4,
        decimal_places=2,
        help_text=_("Vacation weeks for a full year."),
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
