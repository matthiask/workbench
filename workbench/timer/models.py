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
from workbench.tools.formats import Z1, local_date_format


TIMESTAMPS_DETECT_GAP = 300  # seconds


class Slice(dict):
    @property
    def has_associated_log(self):
        return bool(self.get("logged_hours") or self.get("logged_break"))

    @property
    def elapsed_hours(self):
        if self.get("logged_hours"):
            return self["logged_hours"].hours
        elif self.get("logged_break"):
            seconds = self["logged_break"].timedelta.total_seconds()
        elif self.get("starts_at") and self.get("ends_at"):
            seconds = (self["ends_at"] - self["starts_at"]).total_seconds()
        elif not self.get("starts_at") and self.get("ends_at"):
            # STOP only; no way to prefill a nonzero elapsed hours value
            return Decimal(0)
        else:
            return None
        return Decimal(seconds / 3600).quantize(Z1, rounding=ROUND_UP)

    @property
    def hours_create_url(self):
        if self.has_associated_log:
            return None

        params = [
            ("rendered_on", self["day"].isoformat()),
            ("description", self["description"]),
            ("hours", self.elapsed_hours),
        ]
        if self.get("timestamp_id"):
            params.append(("timestamp", self["timestamp_id"]))
        else:  # No timestamp ID and no associated log -- it's a detected slice!
            params.append(("detected_ends_at", self["ends_at"]))

        # Keep zero too (see elapsed_hours above)
        query = urlencode([pair for pair in params if pair[1] or pair[1] == 0])

        return "{}?{}".format(reverse("logbook_loggedhours_create"), query)

    @property
    def break_create_url(self):
        if self.has_associated_log:
            return None

        params = [
            ("day", self["day"].isoformat()),
            ("description", self["description"]),
            ("starts_at", local_date_format(self.get("starts_at"), fmt="H:i:s")),
            ("ends_at", local_date_format(self.get("ends_at"), fmt="H:i:s")),
        ]
        if self.get("timestamp_id"):
            params.append(("timestamp", self["timestamp_id"]))
        else:  # No timestamp ID and no associated log -- it's a detected slice!
            params.append(("detected_ends_at", self["ends_at"]))

        return "{}?{}".format(
            reverse("logbook_break_create"),
            urlencode([pair for pair in params if pair[1]]),
        )


class TimestampQuerySet(models.QuerySet):
    def slices(self, user, *, day=None):
        """
        Create a list of slices from timestamps, logged hours and breaks

        The algorithm works as follows:

        1. Aggregate all timestamps into a list of ``Slice()`` objects. Slices
        and unsaved timestamps are also generated from logged hours and breaks
        without a timestamp linking them.
            a. STOP timestamps' ``created_at`` field denotes the end of a slice.
            b. START timestamps' ``created_at`` field denotes the start of a slice.
            c. Timestamps having a logged hours object use the ``hours`` field
               to either fill in the start of a slice (for STOP timestamps) or the
               end of a slice (for START timestamps).
            d. Breaks have a start and an end so those values are used directly
            e. Logged hours without a timestamp are treated as STOP timestamps,
               the ``created_at`` field of logged hours is treated as timestamp
               creation date.
        2. Merge overlapping slices or generate slices from gaps.
            a. A START timestamp opening a slice is merged with the next slice
               if the next timestamp wasn't a START and the START timestamp does
               not have an associated logbook entry.
            b. The overlap detection algorithm also takes logged hours into
               account by comparing the start of subsequent slices to the
               ``TIMESTAMPS_DETECT_GAP``.
            c. If the gap between two slices is longer than
               ``TIMESTAMPS_DETECT_GAP`` (300 seconds or 5 minutes) the algorithm
               detects a missing gap.
        3. Update the start and end of all slices now that slices have been merged
           and/or detected.
        """
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

        # 1. Create slices
        slices = []
        for entry in entries:
            slice = Slice(
                day=day,
                description=entry.logged_hours or entry.logged_break or entry.notes,
                logged_hours=entry.logged_hours,
                logged_break=entry.logged_break,
                timestamp_id=entry.id,
                is_start=entry.type == entry.START,
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

            slices.append(slice)

        # 2. Merge overlapping slices or generate slices from gaps
        previous = None
        result = []
        for slice in slices:
            if previous is None:
                result.append(slice)
                previous = slice
                continue

            if (
                previous["is_start"]
                and not previous.has_associated_log
                and not slice["is_start"]
            ):
                if not slice.has_associated_log:
                    previous.update(
                        {
                            "timestamp_id": slice["timestamp_id"],
                            "logged_hours": slice["logged_hours"],
                            "logged_break": slice["logged_break"],
                            "is_start": False,  # Not anymore
                            "description": "; ".join(
                                filter(
                                    None,
                                    [
                                        str(previous["description"]),
                                        str(slice["description"]),
                                    ],
                                )
                            ),
                            "ends_at": slice["ends_at"],
                        }
                    )
                    previous = slice
                    continue

                else:
                    gap = (slice["starts_at"] - previous["starts_at"]).total_seconds()
                    if gap <= TIMESTAMPS_DETECT_GAP:
                        result[-1] = slice
                        previous = slice
                        continue

            if slice.get("starts_at") and previous.get("ends_at"):
                gap = (slice["starts_at"] - previous["ends_at"]).total_seconds()
                if gap > TIMESTAMPS_DETECT_GAP:
                    result.append(
                        Slice(
                            day=day,
                            description="",
                            comment=gettext("<detected>"),
                            starts_at=previous["ends_at"],
                            ends_at=slice["starts_at"],
                            is_start=False,
                        )
                    )

            result.append(slice)
            previous = slice

        # 3. Fill in boundaries
        for previous, slice in zip(result, result[1:]):
            boundary = previous.get("ends_at") or slice.get("starts_at")
            slice["starts_at"] = previous["ends_at"] = boundary

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
        Break,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("break"),
    )

    objects = TimestampQuerySet.as_manager()

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("timestamp")
        verbose_name_plural = _("timestamps")

    def save(self, *args, **kwargs):
        assert self.type in {self.START, self.STOP}, "Not to be used for timestamps"
        super().save(*args, **kwargs)

    save.alters_data = True

    def __str__(self):
        return "{:>5} {}".format(self.pretty_time, self.notes)

    @property
    def pretty_time(self):
        return local_date_format(self.created_at, fmt="H:i")
