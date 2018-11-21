from contextlib import contextmanager
from datetime import date, timedelta
from threading import local

from django.db import models
from django.urls import reverse
from django.utils.dates import WEEKDAYS
from django.utils.functional import lazy
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.middleware import set_user_name
from workbench.accounts.models import User
from workbench.tools.models import Model
from workbench.tools.urls import model_urls


_local = local()
current_app = lazy(lambda: getattr(_local, "app", None), str)()


@contextmanager
def activate_app(app):
    _local.app = app
    yield
    _local.app = ""


class App(Model):
    title = models.CharField(_("app"), max_length=100)
    slug = models.SlugField(_("slug"), unique=True)
    ordering = models.IntegerField(_("ordering"), default=0)
    users = models.ManyToManyField(User, related_name="apps", verbose_name=_("users"))

    class Meta:
        ordering = ["ordering"]
        verbose_name = _("app")
        verbose_name_plural = _("apps")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("calendar_day_list", kwargs={"app": self.slug})

    def create_days(self, year=None):
        set_user_name("Solomon")

        year = date.today().year if year is None else year
        defaults = {
            default.day_of_week: default.user
            for default in DayOfWeekDefault.objects.filter(app=self)
        }

        start = date(year, 1, 1)
        for offset in range(0, 366):
            day = start + timedelta(days=offset)
            if day.isoweekday() <= 5 and day.year == year:
                Day.objects.get_or_create(
                    app=self,
                    day=day,
                    defaults={"handled_by": defaults.get(day.isoweekday() - 1)},
                )


class DayQuerySet(models.QuerySet):
    def search(self, terms):
        return self


@model_urls(lambda obj: {"app": current_app, "pk": obj.pk})
class Day(Model):
    app = models.ForeignKey(
        App, on_delete=models.CASCADE, related_name="days", verbose_name=_("app")
    )
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

    @classmethod
    def allow_create(cls, request):
        return False

    @classmethod
    def allow_delete(cls, instance, request):
        return False

    def css(self):
        today = date.today()
        return " ".join(
            filter(
                None,
                [
                    self.day == today and "bg-primary",
                    self.day < today and "text-muted",
                    self.day >= today and not self.handled_by and "text-warning",
                ],
            )
        )


@model_urls()
class Presence(Model):
    app = models.ForeignKey(
        App, on_delete=models.CASCADE, related_name="presences", verbose_name=_("app")
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="+", verbose_name=_("user")
    )
    year = models.IntegerField(_("year"))
    percentage = models.IntegerField(_("percentage"))

    class Meta:
        unique_together = [("user", "year")]
        verbose_name = _("presence")
        verbose_name_plural = _("presences")

    def __str__(self):
        return "{}%".format(self.percentage)


class DayOfWeekDefault(Model):
    app = models.ForeignKey(
        App, on_delete=models.CASCADE, related_name="+", verbose_name=_("app")
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="+", verbose_name=_("user")
    )
    day_of_week = models.IntegerField(
        _("day of week"), choices=sorted(WEEKDAYS.items())
    )

    class Meta:
        unique_together = [("app", "day_of_week")]
        verbose_name = _("day of week default")
        verbose_name_plural = _("day of week defaults")

    def __str__(self):
        return self.get_day_of_week_display()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        Day.objects.filter(
            app=self.app, day__week_day=(self.day_of_week + 1) % 7 + 1, handled_by=None
        ).update(handled_by=self.user)

    save.alters_data = True
