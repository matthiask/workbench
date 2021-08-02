import datetime as dt
from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.services.models import ServiceType
from workbench.tools.formats import hours, local_date_format
from workbench.tools.models import HoursField, Model
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


@model_urls
class PublicHoliday(Model):
    date = models.DateField(_("date"))
    name = models.CharField(_("name"), max_length=200)
    fraction = models.DecimalField(
        _("fraction of day which is free"), default=1, max_digits=5, decimal_places=2
    )

    class Meta:
        ordering = ["-date"]
        verbose_name = _("public holiday")
        verbose_name_plural = _("public holidays")

    def __str__(self):
        return self.name


@model_urls
class Milestone(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("project"),
        related_name="milestones",
    )
    date = models.DateField(_("date"))
    title = models.CharField(_("title"), max_length=200)

    phase_starts_on = models.DateField(
        _("succeeds a phase and starts on"), blank=True, null=True
    )

    estimated_total_hours = HoursField(
        _("planned hours"),
        validators=[MinValueValidator(Decimal("0.0"))],
        default=Decimal("0.0"),
    )

    class Meta:
        ordering = ["date"]
        verbose_name = _("milestone")
        verbose_name_plural = _("milestones")

    def __str__(self):
        return f"{self.title} ({local_date_format(self.date, fmt='l, j.n.')})"


class AbstractPlannedWork(Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("created by"),
        related_name="+",
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("milestone"),
    )
    title = models.CharField(_("title"), max_length=200)
    notes = models.TextField(_("notes"), blank=True)
    weeks = ArrayField(models.DateField(), verbose_name=_("weeks"))
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("primary service type"),
        related_name="+",
    )

    class Meta:
        abstract = True

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}

        if self.weeks:
            no_mondays = [day for day in self.weeks if day.weekday() != 0]
            if no_mondays:
                errors["weeks"] = _("Only mondays allowed, but field contains %s.") % (
                    ", ".join(local_date_format(day) for day in no_mondays),
                )

        raise_if_errors(errors, exclude)

    @property
    def pretty_from_until(self):
        return "{} – {}".format(
            local_date_format(min(self.weeks)),
            local_date_format(max(self.weeks) + dt.timedelta(days=6)),
        )

    @property
    def ranges(self):
        def _find_ranges(weeks):
            start = weeks[0]
            maybe_end = weeks[0]
            for day in weeks[1:]:
                if (day - maybe_end).days == 7:
                    maybe_end = day
                else:
                    yield start, maybe_end
                    start = maybe_end = day

            yield start, maybe_end

        for from_, until_ in _find_ranges(self.weeks):
            yield {
                "from": from_,
                "until": until_,
                "pretty": "{} – {}".format(
                    local_date_format(from_),
                    local_date_format(until_ + dt.timedelta(days=6)),
                ),
            }

    @property
    def pretty_planned_hours(self):
        return _("%(planned_hours)s in %(weeks)s weeks (%(per_week)s per week)") % {
            "planned_hours": hours(self.planned_hours),
            "weeks": len(self.weeks),
            "per_week": hours(self.planned_hours / len(self.weeks)),
        }


@model_urls
class ExternalWork(AbstractPlannedWork):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("project"),
        related_name="external_work",
    )
    provided_by = models.CharField(_("provided by"), max_length=200)

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("external work")
        verbose_name_plural = _("external work")

    def __str__(self):
        return "{}: {}".format(self.provided_by, self.title)


@model_urls
class PlannedWork(AbstractPlannedWork):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("project"),
        related_name="planned_work",
    )
    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("offer"),
        related_name="planned_work",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("user"),
        related_name="planned_work",
    )
    planned_hours = HoursField(
        _("planned hours"), validators=[MinValueValidator(Decimal("0.1"))]
    )
    is_provisional = models.BooleanField(_("is provisional"), default=False)

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("planned work")
        verbose_name_plural = _("planned work")

    def __str__(self):
        return "{} ({})".format(self.title, hours(self.planned_hours))
