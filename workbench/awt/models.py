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
from workbench.tools.models import Model, HoursField, Z
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
        return reverse("awt_year_report") + "?year={}".format(self.year)

    @property
    def months(self):
        return [getattr(self, field) for field in self.MONTHS]

    def statistics(self, *, users=None):
        if users is None:
            users = User.objects.filter(is_active=True)

        target_days = list(self.months)

        absences = defaultdict(lambda: {"vacation_days": [], "other_absences": []})
        months = defaultdict(
            lambda: {
                "months": [None] * 12,
                "target_days": target_days,
                "percentage": [Z for i in range(12)],
                "available_vacation_days": [Z for i in range(12)],
                "vacation_days": [Z for i in range(12)],
                "vacation_days_correction": [Z for i in range(12)],
                "other_absences": [Z for i in range(12)],
                "target": [Z for i in range(12)],
                "hours": [Z for i in range(12)],
            }
        )
        dpm = days_per_month(self.year)

        for employment in Employment.objects.filter(user__in=users).order_by(
            "-date_from"
        ):
            percentage_factor = Decimal(employment.percentage) / 100
            available_vacation_days_per_month = (
                Decimal(employment.vacation_weeks) * 5 / 12 * percentage_factor
            )
            month_data = months[employment.user_id]
            for month, days in monthly_days(
                employment.date_from, employment.date_until
            ):
                if month.year < self.year:
                    continue
                elif month.year > self.year:
                    break
                partial_month_factor = Decimal(days) / dpm[month.month - 1]
                month_data["target"][month.month - 1] -= (
                    target_days[month.month - 1]
                    * percentage_factor
                    * partial_month_factor
                )
                month_data["percentage"][month.month - 1] += (
                    100 * percentage_factor * partial_month_factor
                )
                month_data["available_vacation_days"][month.month - 1] += (
                    available_vacation_days_per_month * partial_month_factor
                )
                month_data["months"][month.month - 1] = month

        for row in (
            LoggedHours.objects.order_by()
            .filter(rendered_by__in=users, rendered_on__year=self.year)
            .values("rendered_by")
            .annotate(month=ExtractMonth("rendered_on"))
            .values("rendered_by", "month")
            .annotate(Sum("hours"))
        ):
            months[row["rendered_by"]]["hours"][row["month"] - 1] += row["hours__sum"]

        remaining = {
            user: sum(month_data["available_vacation_days"])
            for user, month_data in months.items()
        }
        for absence in Absence.objects.filter(
            user__in=users, starts_on__year=self.year
        ).order_by("starts_on"):
            key = "vacation_days" if absence.is_vacation else "other_absences"
            absences[absence.user_id][key].append(absence)
            month_data = months[absence.user_id]
            month_data[key][absence.starts_on.month - 1] += absence.days

            if absence.is_vacation:
                if absence.days > remaining[absence.user_id]:
                    month_data["vacation_days_correction"][
                        absence.starts_on.month - 1
                    ] += (remaining[absence.user_id] - absence.days)
                remaining[absence.user_id] = max(
                    0, remaining[absence.user_id] - absence.days
                )

        for user_id, vacation_days in remaining.items():
            if vacation_days > 0:
                months[user_id]["vacation_days_correction"][11] = vacation_days

        today = date.today()
        this_month = (today.year, today.month - 1)

        def working_time(data):
            return [
                sum(
                    (
                        data["hours"][i] / self.working_time_per_day,
                        data["vacation_days"][i],
                        data["vacation_days_correction"][i],
                        data["other_absences"][i],
                    ),
                    Z,
                )
                for i in range(12)
            ]

        def monthly_sums(data):
            sums = [None] * 12
            for i in range(12):
                if (self.year, i) >= this_month:
                    break
                sums[i] = data["hours"][i] + self.working_time_per_day * sum(
                    (
                        data["vacation_days"][i],
                        data["vacation_days_correction"][i],
                        data["other_absences"][i],
                        data["target"][i],
                    )
                )
            return sums

        statistics = []
        for user in users:
            user_data = months[user.id]
            sums = monthly_sums(user_data)
            wt = working_time(user_data)
            statistics.append(
                {
                    "user": user,
                    "months": user_data,
                    "absences": absences[user.id],
                    "working_time": wt,
                    "monthly_sums": sums,
                    "totals": {
                        "target_days": sum(user_data["target_days"]),
                        "percentage": sum(user_data["percentage"]) / 12,
                        "available_vacation_days": sum(
                            user_data["available_vacation_days"]
                        ),
                        "vacation_days": sum(user_data["vacation_days"]),
                        "vacation_days_correction": sum(
                            user_data["vacation_days_correction"]
                        ),
                        "other_absences": sum(user_data["other_absences"]),
                        "target": sum(user_data["target"]),
                        "hours": sum(user_data["hours"]),
                        "working_time": sum(wt),
                        "running_sum": sum(filter(None, sums), Z),
                    },
                }
            )

        return statistics


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
