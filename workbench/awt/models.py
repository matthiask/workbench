import datetime as dt

from django.contrib import messages
from django.db import models
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.tools.formats import hours, local_date_format
from workbench.tools.models import HoursField, Model, MoneyField
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


class WorkingTimeModel(models.Model):
    name = models.CharField(_("name"), max_length=100)
    position = models.IntegerField(_("position"), default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("working time model")
        verbose_name_plural = _("working time models")

    def __str__(self):
        return self.name


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

    working_time_model = models.ForeignKey(
        WorkingTimeModel,
        on_delete=models.CASCADE,
        verbose_name=_("working time model"),
    )
    year = models.IntegerField(_("year"))
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
        unique_together = (("working_time_model", "year"),)
        verbose_name = _("year")
        verbose_name_plural = _("years")

    def __str__(self):
        return "%s %s" % (self.year, self.working_time_model)

    @property
    def months(self):
        return [getattr(self, field) for field in self.MONTHS]

    @property
    def pretty_working_time_per_day(self):
        return "%s/%s" % (hours(self.working_time_per_day), _("day"))


class Employment(Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="employments",
    )
    date_from = models.DateField(_("date from"), default=dt.date.today)
    date_until = models.DateField(_("date until"), default=dt.date.max)
    percentage = models.IntegerField(_("percentage"))
    vacation_weeks = models.DecimalField(
        _("vacation weeks"),
        max_digits=4,
        decimal_places=2,
        help_text=_("Vacation weeks for a full year."),
    )
    notes = models.CharField(_("notes"), blank=True, max_length=500)
    hourly_labor_costs = MoneyField(_("hourly labor costs"), blank=True, null=True)
    green_hours_target = models.SmallIntegerField(
        _("green hours target"), blank=True, null=True
    )

    class Meta:
        ordering = ["date_from"]
        unique_together = ["user", "date_from"]
        verbose_name = _("employment")
        verbose_name_plural = _("employments")

    def __str__(self):
        if self.date_until.year > 3000:
            return _("since %s") % local_date_format(self.date_from)
        return "%s - %s" % (
            local_date_format(self.date_from),
            local_date_format(self.date_until),
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        next = None
        for employment in self.user.employments.reverse():
            if next is None:
                next = employment
            else:
                if employment.date_until >= next.date_from:
                    employment.date_until = next.date_from - dt.timedelta(days=1)
                    super(Employment, employment).save()
                next = employment

    save.alters_data = True

    def clean_fields(self, exclude):
        super().clean_fields(exclude)
        errors = {}
        if (self.hourly_labor_costs is None) != (self.green_hours_target is None):
            errors["__all__"] = _(
                "Either provide both hourly labor costs"
                " and green hours target or none."
            )
        if self.date_from and self.date_until and self.date_from > self.date_until:
            errors["date_until"] = _("Employments cannot end before they began.")
        raise_if_errors(errors, exclude)


@model_urls
class Absence(Model):
    VACATION = "vacation"
    SICKNESS = "sickness"
    PAID = "paid"
    OTHER = "other"
    CORRECTION = "correction"

    REASON_CHOICES = [
        (VACATION, _("vacation")),
        (SICKNESS, _("sickness")),
        (PAID, _("paid leave (e.g. civilian service, maternity etc.)")),
        (OTHER, _("other reasons (no working time)")),
        (CORRECTION, _("Working time correction")),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_("user"), related_name="absences"
    )
    starts_on = models.DateField(_("starts on"))
    ends_on = models.DateField(_("ends on"), blank=True, null=True)
    days = models.DecimalField(_("days"), max_digits=4, decimal_places=2)
    description = models.TextField(_("description"))
    reason = models.CharField(_("reason"), max_length=10, choices=REASON_CHOICES)
    is_vacation = models.BooleanField(_("is vacation"), default=True)
    is_working_time = models.BooleanField(_("is working time"), default=True)

    class Meta:
        ordering = ["-starts_on", "-pk"]
        verbose_name = _("absence")
        verbose_name_plural = _("absences")

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        self.is_vacation = self.reason == self.VACATION
        self.is_working_time = self.reason != self.OTHER
        super().save(*args, **kwargs)

    save.alters_data = True

    @classmethod
    def allow_update(cls, instance, request):
        if (
            instance.user.enforce_same_week_logging
            and instance.starts_on.year < dt.date.today().year
        ):
            messages.error(request, _("Absences of past years are locked."))
            return False
        if (
            instance.reason == instance.CORRECTION
            and not request.user.features[FEATURES.WORKING_TIME_CORRECTION]
        ):
            messages.error(
                request,
                _(
                    "You are not permitted to edit absences"
                    " of type «Working time correction»."
                ),
            )
            return False
        return True

    allow_delete = allow_update

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return cls.urls["list"] + "?u={}".format(
                instance.user_id if instance else ""
            )

    def clean_fields(self, exclude):
        super().clean_fields(exclude)
        errors = {}
        if self.starts_on and self.ends_on:
            if self.ends_on < self.starts_on:
                errors["ends_on"] = _("Absences cannot end before they began.")
            if self.starts_on.year != self.ends_on.year:
                errors["ends_on"] = _("Start and end must be in the same year.")
        raise_if_errors(errors, exclude)

    @property
    def pretty_status(self):
        return "%s, %s" % (gettext("%s days") % self.days, self.pretty_period)

    @property
    def pretty_period(self):
        return "%s - %s" % (
            local_date_format(self.starts_on),
            local_date_format(self.ends_on or self.starts_on),
        )
