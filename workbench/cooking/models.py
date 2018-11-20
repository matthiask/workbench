from datetime import date, timedelta

from django.db import models
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.models import Model
from workbench.tools.urls import model_urls


class DayQuerySet(models.QuerySet):
    def create_days(self):
        today = date.today()
        latest = self.order_by("-day").first()
        start_from = max(0, (latest.day - today).days if latest else 0)
        for offset in range(start_from, 180):
            day = today + timedelta(days=offset)
            if 0 < day.weekday() < 6:  # No weekends
                self.get_or_create(day=today + timedelta(days=offset))


@model_urls()
class Day(Model):
    day = models.DateField(_("day"))
    handled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        verbose_name=_("handled by"),
    )

    objects = DayQuerySet.as_manager()

    class Meta:
        ordering = ["day"]
        verbose_name = _("day")
        verbose_name_plural = _("days")

    def __str__(self):
        return "{} - {}".format(self.day, self.handled_by or "?")
