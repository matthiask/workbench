from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.formats import Z1, hours, local_date_format
from workbench.tools.models import HoursField, Model, SearchQuerySet
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


class PlanningTeamMembership(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("project"),
        related_name="planning_team_memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="planning_team_memberships",
    )

    class Meta:
        verbose_name = _("planning team membership")
        verbose_name_plural = _("planning team memberships")

    def __str__(self):
        return "{} <--> {}".format(self.project, self.user)


class PlanningRequestQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(
            Q(closed_at__isnull=True),
            Q(project__closed_on__isnull=True),
            Q(offer__isnull=True) | Q(offer__in=Offer.objects.not_declined()),
        )


@model_urls
class PlanningRequest(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("project"),
        related_name="planning_requests",
    )
    offer = models.ForeignKey(
        Offer,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("offer"),
        related_name="planning_requests",
    )
    requested_hours = HoursField(_("requested hours"))
    planned_hours = HoursField(_("planned hours"))
    earliest_start_on = models.DateField(_("earliest start on"))
    completion_requested_on = models.DateField(_("completion requested on"))
    title = models.CharField(_("title"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    receivers = models.ManyToManyField(
        User, verbose_name=_("receivers"), related_name="received_planning_requests"
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("created by"),
        related_name="sent_planning_requests",
    )
    closed_at = models.DateTimeField(_("closed at"), blank=True, null=True)

    objects = PlanningRequestQuerySet.as_manager()

    class Meta:
        ordering = ["earliest_start_on", "completion_requested_on"]
        verbose_name = _("planning request")
        verbose_name_plural = _("planning requests")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            self.planned_hours = (
                self.planned_work.order_by().aggregate(h=Sum("planned_hours"))["h"]
                or Z1
            )
        else:
            self.planned_hours = Z1
        super().save(*args, **kwargs)

    save.alters_data = True

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}

        if self.earliest_start_on.weekday() != 0:
            errors["earliest_start_on"] = _("Only mondays allowed.")
        if self.completion_requested_on.weekday() != 0:
            errors["completion_requested_on"] = _("Only mondays allowed.")

        if self.completion_requested_on <= self.earliest_start_on:
            errors["completion_requested_on"] = _(
                "Allow at least one week for the work please."
            )

        raise_if_errors(errors, exclude)


@model_urls
class PlannedWork(Model):
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
    request = models.ForeignKey(
        PlanningRequest,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("planning request"),
        related_name="planned_work",
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("user"),
        related_name="planned_work",
    )
    planned_hours = HoursField(_("planned hours"))
    notes = models.TextField(_("notes"), blank=True)
    weeks = ArrayField(models.DateField(), verbose_name=_("weeks"))

    class Meta:
        ordering = ["weeks"]
        verbose_name = _("planned work")
        verbose_name_plural = _("planned work")

    def __str__(self):
        return hours(self.planned_hours)

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}

        no_mondays = [day for day in self.weeks if day.weekday() != 0]
        if no_mondays:
            errors["weeks"] = _("Only mondays allowed, but field contains %s.") % (
                ", ".join(local_date_format(day) for day in no_mondays),
            )

        raise_if_errors(errors, exclude)
