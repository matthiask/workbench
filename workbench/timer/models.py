import datetime as dt
from decimal import ROUND_UP, Decimal

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
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


class Timestamp(models.Model):
    START = "start"
    SPLIT = "split"
    STOP = "stop"
    LOGBOOK = "logbook"

    TYPE_CHOICES = [
        (START, _("start")),
        (SPLIT, _("split")),
        (STOP, _("stop")),
        (LOGBOOK, _("logbook")),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    type = models.CharField(_("type"), max_length=10, choices=TYPE_CHOICES)
    notes = models.CharField(_("notes"), max_length=500, blank=True)

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("timestamp")
        verbose_name_plural = _("timestamps")

    def __str__(self):
        return local_date_format(self.created_at)

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
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            css[self.type],
            self.get_type_display(),
        )

    @classmethod
    def for_user(cls, user, *, day=None):
        day = day or dt.date.today()
        entries = list(cls.objects.filter(user=user, created_at__date=day))
        entries.extend(
            cls(
                created_at=entry.created_at,
                type=cls.LOGBOOK,
                notes=_("Logbook entry on %(service)s: %(description)s (%(hours)s)")
                % {
                    "service": entry.service,
                    "description": entry.description,
                    "hours": hours(entry.hours),
                },
                url=entry.get_absolute_url(),
            )
            for entry in user.loggedhours.filter(rendered_on=day).select_related(
                "service"
            )
        )
        if not entries:
            return []
        entries = sorted(entries, key=lambda timestamp: timestamp.created_at)

        ret = []
        previous = None
        for current in entries:
            if previous is None or previous.type == Timestamp.STOP:
                if current.type == Timestamp.STOP:
                    # Skip
                    continue

                if current.type not in {Timestamp.START, Timestamp.LOGBOOK}:
                    current.type = Timestamp.START  # Override
                elapsed = None

            elif current.type in {Timestamp.LOGBOOK}:
                elapsed = None

            else:
                if previous and {previous.type, current.type} == {Timestamp.START}:
                    current.type = Timestamp.SPLIT  # Override

                seconds = (current.created_at - previous.created_at).total_seconds()
                elapsed = (Decimal(seconds) / 3600).quantize(
                    Decimal("0.0"), rounding=ROUND_UP
                )

            ret.append({"timestamp": current, "elapsed": elapsed})
            previous = current

        return ret
