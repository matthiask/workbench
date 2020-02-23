import datetime as dt
from decimal import ROUND_UP, Decimal

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.formats import local_date_format


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
    def structured(self, *, day=None):
        day = day or dt.date.today()
        entries = list(self.filter(created_at__date=day).order_by("pk"))
        if not entries:
            return []

        ret = []
        previous = None
        for current in entries:
            if previous is None and current.type == Timestamp.STOP:
                # Skip
                continue

            if previous is None or previous.type == Timestamp.STOP:
                seconds = 0
                current.type = Timestamp.START  # Override
            else:
                seconds = (current.created_at - previous.created_at).total_seconds()
            elapsed = (Decimal(seconds) / 3600).quantize(
                Decimal("0.0"), rounding=ROUND_UP
            )
            ret.append({"timestamp": current, "elapsed": elapsed})
            previous = current

        return ret


class Timestamp(models.Model):
    START = "start"
    SPLIT = "split"
    STOP = "stop"

    TYPE_CHOICES = [(START, _("start")), (SPLIT, _("split")), (STOP, _("stop"))]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    type = models.CharField(_("type"), max_length=10, choices=TYPE_CHOICES)
    notes = models.CharField(_("notes"), max_length=500, blank=True)

    objects = TimestampQuerySet.as_manager()

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("timestamp")
        verbose_name_plural = _("timestamps")

    def __str__(self):
        return local_date_format(self.created_at)
