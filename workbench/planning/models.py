import datetime as dt
from decimal import Decimal
from itertools import takewhile

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum, signals
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from authlib.email import render_to_mail

from workbench.accounts.models import User
from workbench.invoices.utils import recurring
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.formats import Z1, hours, local_date_format
from workbench.tools.models import HoursField, Model, SearchQuerySet
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


class PlanningRequestQuerySet(SearchQuerySet):
    def with_missing_hours(self):
        return self.annotate(
            _missing_hours=F("requested_hours") - F("planned_hours")
        ).filter(project__closed_on__isnull=True, _missing_hours__gt=0)

    def maybe_actionable(self, *, user):
        return (
            self.with_missing_hours().filter(receivers=user).select_related("project")
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
    requested_hours = HoursField(
        _("requested hours"), validators=[MinValueValidator(Decimal("0.1"))]
    )
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
    is_provisional = models.BooleanField(_("is provisional"), default=False)

    objects = PlanningRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-pk"]
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

    @cached_property
    def weeks(self):
        return list(
            takewhile(
                lambda x: x < self.completion_requested_on,
                recurring(self.earliest_start_on, "weekly"),
            )
        )

    @cached_property
    def receivers_with_work(self):
        work = {user: [] for user in self.receivers.all()}
        for pw in self.planned_work.select_related("user"):
            work.setdefault(pw.user, []).append(pw)
        return sorted(work.items())

    @property
    def missing_hours(self):
        return self.requested_hours - self.planned_hours

    def html_link(self):
        return format_html(
            '<a href="{}" data-toggle="ajaxmodal">{}</a>', self.get_absolute_url(), self
        )


def receivers_changed(sender, action, instance, pk_set, **kwargs):
    if action == "post_add":
        users = User.objects.filter(pk__in=pk_set)
        render_to_mail(
            "planning/planningrequest_notification",
            {"object": instance, "WORKBENCH": settings.WORKBENCH},
            to=[user.email for user in users],
            cc=[instance.created_by.email],
            reply_to=[instance.created_by.email] + [user.email for user in users],
        ).send(fail_silently=True)


signals.m2m_changed.connect(receivers_changed, sender=PlanningRequest.receivers.through)


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
    planned_hours = HoursField(
        _("planned hours"), validators=[MinValueValidator(Decimal("0.1"))]
    )
    title = models.CharField(_("title"), max_length=200)
    notes = models.TextField(_("notes"), blank=True)
    weeks = ArrayField(models.DateField(), verbose_name=_("weeks"))

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("planned work")
        verbose_name_plural = _("planned work")

    def __str__(self):
        return "{} ({})".format(self.title, hours(self.planned_hours))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_request_ids = {self.request_id}

    def _update_requests(self):
        self._update_request_ids.add(self.request_id)
        self._update_request_ids.discard(None)
        if self._update_request_ids:
            for request in PlanningRequest.objects.filter(
                id__in=self._update_request_ids
            ):
                request.save()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_requests()

    save.alters_data = False

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._update_requests()

    delete.alters_data = False

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
