import datetime as dt
from decimal import ROUND_UP, Decimal

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.logbook.models import Break, LoggedHours
from workbench.tools.formats import hours, local_date_format


class TimerState(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name=_("user"))
    state = JSONField(_("state"), default=dict)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("timer state")
        verbose_name_plural = _("timer states")

    def __str__(self):
        return str(self.user)


class TimestampQuerySet(models.QuerySet):
    def for_user(self, user, *, day=None):
        day = day or dt.date.today()
        entries = list(
            self.filter(user=user, created_at__date=day).select_related(
                "logged_hours__service", "logged_break"
            )
        )
        known_logged_hours = set(entry.logged_hours for entry in entries)
        logged_hours = user.loggedhours.filter(rendered_on=day).select_related(
            "service"
        )
        entries.extend(
            self.model(
                created_at=entry.created_at,
                type=self.model.LOGBOOK,
                notes=_("Logbook entry on %(service)s: %(description)s (%(hours)s)")
                % {
                    "service": entry.service,
                    "description": entry.description,
                    "hours": hours(entry.hours),
                },
                url=entry.get_absolute_url(),
                logged_hours=entry,
            )
            for entry in logged_hours
            if entry not in known_logged_hours
        )
        if not entries:
            return {"timestamps": [], "hours": Decimal(0)}

        entries = sorted(entries, key=lambda timestamp: timestamp.created_at)

        ret = []
        previous = None
        for current in entries:
            if previous is None or previous.type == Timestamp.STOP:
                if current.type == Timestamp.STOP:
                    # Skip
                    continue

                if current.type not in {
                    Timestamp.START,
                    Timestamp.LOGBOOK,
                    Timestamp.BREAK,
                }:
                    current.type = Timestamp.START  # Override
                elapsed = None

            elif current.type in {Timestamp.LOGBOOK}:
                current_started_at = current.created_at - dt.timedelta(
                    hours=float(current.logged_hours.hours)
                )
                seconds = Decimal(
                    (current_started_at - previous.created_at).total_seconds()
                )

                if seconds > 600:  # Arbitrary cut-off
                    entry = self.model(
                        id=0,
                        created_at=current_started_at,
                        type=self.model.START,
                        notes="",
                    )
                    entry.comment = _("Maybe the start of the next logbook entry?")
                    ret.append(
                        {
                            "timestamp": entry,
                            "previous": previous,
                            "elapsed": (seconds / 3600).quantize(
                                Decimal("0.0"), rounding=ROUND_UP
                            ),
                        }
                    )
                    previous = entry

                elapsed = None

            else:
                if previous and {previous.type, current.type} == {Timestamp.START}:
                    current.type = Timestamp.SPLIT  # Override

                seconds = (current.created_at - previous.created_at).total_seconds()
                elapsed = (Decimal(seconds) / 3600).quantize(
                    Decimal("0.0"), rounding=ROUND_UP
                )

            ret.append({"timestamp": current, "previous": previous, "elapsed": elapsed})
            previous = current

        return {
            "timestamps": ret,
            "hours": sum((hours.hours for hours in logged_hours), Decimal(0)),
        }


class Timestamp(models.Model):
    START = "start"
    SPLIT = "split"
    STOP = "stop"
    LOGBOOK = "logbook"
    BREAK = "break"

    TYPE_CHOICES = [
        (START, _("Start")),
        (SPLIT, _("Split")),
        (STOP, _("Stop")),
        (LOGBOOK, capfirst(_("logbook"))),
        (BREAK, capfirst(_("break"))),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    type = models.CharField(_("type"), max_length=10, choices=TYPE_CHOICES)
    notes = models.CharField(_("notes"), max_length=500, blank=True)
    logged_hours = models.OneToOneField(
        LoggedHours,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("logged hours"),
    )
    logged_break = models.OneToOneField(
        Break, on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("break"),
    )

    objects = TimestampQuerySet.as_manager()

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("timestamp")
        verbose_name_plural = _("timestamps")

    def __str__(self):
        return "{} @ {}".format(
            self.get_type_display(), local_date_format(self.created_at)
        )

    def __init__(self, *args, **kwargs):
        self.url = kwargs.pop("url", "")
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        assert self.type != self.LOGBOOK, "Not to be used for timestamps"
        super().save(*args, **kwargs)

    save.alters_data = True

    @property
    def badge(self):
        css = {
            self.START: "primary",
            self.SPLIT: "info",
            self.STOP: "success",
            self.LOGBOOK: "secondary",
            self.BREAK: "break",
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            css[self.type],
            self.get_type_display(),
        )

    @property
    def time(self):
        return localtime(self.created_at).time().replace(microsecond=0)

    def get_delete_url(self):
        return reverse("delete_timestamp", args=(self.pk,))
