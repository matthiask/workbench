import datetime as dt
from decimal import ROUND_UP, Decimal
from urllib.parse import urlencode

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import capfirst
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User
from workbench.logbook.models import Break, LoggedHours
from workbench.projects.models import Project
from workbench.tools.formats import Z1, local_date_format


class Slice(dict):
    @property
    def show_create_buttons(self):
        return not (self.get("logged_hours") or self.get("logged_break"))

    @property
    def elapsed_hours(self):
        if self.get("logged_hours"):
            return self["logged_hours"].hours
        elif self.get("logged_break"):
            seconds = self["logged_break"].timedelta.total_seconds()
        elif self.get("starts_at") and self.get("ends_at"):
            seconds = (self["ends_at"] - self["starts_at"]).total_seconds()
        else:
            return None
        return Decimal(seconds / 3600).quantize(Z1, rounding=ROUND_UP)

    @property
    def hours_create_url(self):
        if not self.show_create_buttons:
            return None

        params = [
            ("rendered_on", self["day"].isoformat()),
            ("description", self["description"]),
            ("hours", self.elapsed_hours),
        ]
        if self.get("timestamp_id"):
            params.append(("timestamp", self["timestamp_id"]))
        elif self.show_create_buttons:
            params.append(("detected_ends_at", self["ends_at"]))

        return "{}?{}".format(
            reverse("projects_project_createhours", kwargs={"pk": self["project_id"]})
            if self.get("project_id")
            else reverse("logbook_loggedhours_create"),
            urlencode([pair for pair in params if pair[1]]),
        )

    @property
    def break_create_url(self):
        if not self.show_create_buttons:
            return None

        params = [
            ("day", self["day"].isoformat()),
            ("description", self["description"]),
            ("starts_at", local_date_format(self.get("starts_at"), fmt="H:i:s")),
            ("ends_at", local_date_format(self.get("ends_at"), fmt="H:i:s")),
        ]
        if self.get("timestamp_id"):
            params.append(("timestamp", self["timestamp_id"]))
        elif self.show_create_buttons:
            params.append(("detected_ends_at", self["ends_at"]))

        return "{}?{}".format(
            reverse("logbook_break_create"),
            urlencode([pair for pair in params if pair[1]]),
        )


class TimestampQuerySet(models.QuerySet):
    def slices(self, user, *, day=None):
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
        known_breaks = set(entry.logged_break for entry in entries)
        breaks = user.breaks.filter(starts_at__date=day)
        entries.extend(
            self.model(
                created_at=entry.ends_at, type=self.model.BREAK, logged_break=entry
            )
            for entry in breaks
            if entry not in known_breaks
        )
        entries = sorted(entries, key=lambda timestamp: timestamp.created_at)

        previous = None
        slices = []
        for entry in entries:
            if slices:
                slices[-1].setdefault("ends_at", entry.created_at)

            slice = Slice(
                day=day,
                description=entry.logged_hours or entry.logged_break or entry.notes,
                logged_hours=entry.logged_hours,
                logged_break=entry.logged_break,
                project_id=entry.project_id,
                timestamp_id=entry.id,
            )

            if entry.logged_break:
                slice["starts_at"] = entry.logged_break.starts_at
                slice["ends_at"] = entry.logged_break.ends_at
            elif entry.type == entry.START:
                slice["starts_at"] = entry.created_at
                if entry.logged_hours:
                    slice["ends_at"] = entry.created_at + dt.timedelta(
                        seconds=int(3600 * entry.logged_hours.hours)
                    )
            else:
                slice["ends_at"] = entry.created_at
                if entry.logged_hours:
                    slice["starts_at"] = entry.created_at - dt.timedelta(
                        seconds=int(3600 * entry.logged_hours.hours)
                    )

            if (
                previous
                and previous.type == previous.START
                and not previous.logged_break
                and not previous.logged_hours
                and entry.type != entry.START
                and slice.show_create_buttons
            ):
                slices[-1]["description"] = "; ".join(
                    filter(None, (slices[-1]["description"], entry.notes))
                )
                previous = entry
                continue

            slices.append(slice)

            if previous:
                slices[-1].setdefault("starts_at", previous.created_at)

            previous = entry

        if slices and slice != slices[-1]:
            slices.append(slice)

        if slices and not slices[-1].get("ends_at"):
            if slices[-1]["logged_break"]:
                slices[-1]["ends_at"] = slices[-1]["logged_break"].ends_at
            elif slices[-1]["logged_hours"]:
                slices[-1]["ends_at"] = slices[-1]["logged_hours"].created_at

        previous = None
        result = []
        for slice in slices:
            if previous is not None:
                if slice.get("starts_at") and previous.get("ends_at"):
                    gap = (slice["starts_at"] - previous["ends_at"]).total_seconds()
                    if gap > 300:
                        result.append(
                            Slice(
                                day=day,
                                description="",
                                comment=gettext("<detected>"),
                                starts_at=previous["ends_at"],
                                ends_at=slice["starts_at"],
                            )
                        )
            result.append(slice)
            previous = slice

        return result


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

    def __str__(self):
        return "{:>5} {}".format(self.pretty_time, self.notes)

    @property
    def pretty_time(self):
        return local_date_format(self.created_at, fmt="H:i")
