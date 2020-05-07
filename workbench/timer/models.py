import datetime as dt
from decimal import ROUND_UP, Decimal
from urllib.parse import urlencode

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.logbook.models import Break, LoggedHours
from workbench.projects.models import Project
from workbench.tools.formats import Z0, Z1, hours, local_date_format


def break_create_url(day, current, previous, *, description=None):
    return "{}?{}".format(
        reverse("logbook_break_create"),
        urlencode(
            [
                ("day", day.isoformat()),
                ("description", current.notes if description is None else description),
                ("starts_at", previous.time.isoformat() if previous else "",),
                ("ends_at", current.time.isoformat()),
                ("timestamp", current.pk),
            ]
        ),
    )


def loggedhours_create_url(day, current, elapsed, timestamp_id=None):
    return "{}?{}".format(
        current.get_loggedhours_create_url(),
        urlencode(
            [
                ("description", current.notes),
                ("hours", str(elapsed)),
                ("rendered_on", day.isoformat()),
                ("timestamp", current.pk if timestamp_id is None else timestamp_id),
            ]
        ),
    )


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
                created_at=entry.created_at, type=self.model.LOGBOOK, logged_hours=entry
            )
            for entry in logged_hours
            if entry not in known_logged_hours
        )
        if not entries:
            return {"timestamps": [], "hours": Z0}

        entries = sorted(entries, key=lambda timestamp: timestamp.created_at)

        ret = []
        previous = None
        for current in entries:
            row = {
                "timestamp": current,
                "previous": previous,
                "elapsed": None,
                "break_create_url": break_create_url(day, current, previous),
            }

            if previous:
                seconds = (current.created_at - previous.created_at).total_seconds()
                row["elapsed"] = (Decimal(seconds) / 3600).quantize(
                    Z1, rounding=ROUND_UP
                )

                if {previous.type, current.type} == {Timestamp.START}:
                    row["break_create_url"] = break_create_url(
                        day, current, previous, description=previous.notes
                    )
                    row["loggedhours_create_url"] = loggedhours_create_url(
                        day, previous, row["elapsed"], timestamp_id=current.pk
                    )
                else:
                    row["loggedhours_create_url"] = loggedhours_create_url(
                        day, current, row["elapsed"]
                    )

            ret.append(row)
            previous = current

        return {
            "timestamps": ret,
            "hours": sum((hours.hours for hours in logged_hours), Z0),
        }


class Timestamp(models.Model):
    START = "start"
    STOP = "stop"
    LOGBOOK = "logbook"
    BREAK = "break"

    TYPE_CHOICES = [
        (START, _("Start")),
        (STOP, _("Stop")),
        (LOGBOOK, capfirst(_("logbook"))),
        (BREAK, capfirst(_("break"))),
    ]

    TYPE_DICT = dict(TYPE_CHOICES)

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
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("project"),
    )

    objects = TimestampQuerySet.as_manager()

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("timestamp")
        verbose_name_plural = _("timestamps")

    def save(self, *args, **kwargs):
        assert self.type != self.LOGBOOK, "Not to be used for timestamps"
        super().save(*args, **kwargs)

    save.alters_data = True

    @property
    def pretty_type(self):
        if self.logged_hours:
            return self.LOGBOOK
        elif self.logged_break:
            return self.BREAK
        return self.type

    def __str__(self):
        return "{} @ {}{}{}".format(
            self.TYPE_DICT[self.type],
            self.pretty_time,
            ": " if self.pretty_notes else "",
            self.pretty_notes,
        )

    @property
    def pretty_time(self):
        return local_date_format(self.created_at, fmt="H:i")

    @property
    def pretty_notes(self):
        if self.logged_hours:
            return "{entry} ({hours})".format(
                entry=self.logged_hours, hours=hours(self.logged_hours.hours)
            )

        if self.logged_break:
            return str(self.logged_break)

        return self.notes

    @property
    def badge(self):
        css = {
            self.START: "primary",
            self.STOP: "success",
            self.LOGBOOK: "secondary",
            self.BREAK: "break",
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            css[self.type],
            self.TYPE_DICT[self.type],
        )

    @property
    def time(self):
        return localtime(self.created_at).time().replace(microsecond=0)

    def get_loggedhours_create_url(self):
        return (
            reverse("projects_project_createhours", kwargs={"pk": self.project_id})
            if self.project_id
            else reverse("logbook_loggedhours_create")
        )

    def get_delete_url(self):
        return reverse("delete_timestamp", args=(self.pk,))
