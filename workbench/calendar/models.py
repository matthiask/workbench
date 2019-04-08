from collections import Counter
from contextlib import contextmanager
from datetime import date, timedelta
from threading import local

from django.db import models
from django.db.models import Q, signals
from django.urls import reverse
from django.utils.dates import WEEKDAYS
from django.utils.functional import lazy
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.middleware import set_user_name
from workbench.accounts.models import User
from workbench.tools.formats import local_date_format
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
        set_user_name("Hangar")

        today = date.today()
        year = today.year if year is None else year
        defaults = {
            default.day_of_week: default.user
            for default in DayOfWeekDefault.objects.filter(app=self)
        }

        public_holidays = set(day.day for day in PublicHoliday.objects.all())
        company_holidays = list(CompanyHoliday.objects.all())

        start = date(year, 1, 1)
        for offset in range(0, 366):
            day = start + timedelta(days=offset)
            if day.isoweekday() <= 5 and day.year == year:
                if (
                    day < today
                    or day in public_holidays
                    or any(ch.contains(day) for ch in company_holidays)
                ):
                    continue
                Day.objects.get_or_create(
                    app=self,
                    day=day,
                    defaults={"handled_by": defaults.get(day.isoweekday() - 1)},
                )

    def stats(self, year=None):
        year = date.today().year if year is None else year
        counts = Counter(
            self.days.filter(day__year=year).values_list("handled_by", flat=True)
        )
        presences = dict(
            self.presences.filter(year=year).values_list("user", "percentage")
        )

        users = (
            User.objects.filter(id__in=set(counts.keys()) | set(presences))
            | self.users.all()
        ).distinct()
        presences_sum = sum(presences.values())
        counts_sum = sum(
            (
                count
                for user_id, count in counts.items()
                if user_id in presences or user_id is None
            ),
            0,
        )

        rows = []
        for user in users:
            if user.id in presences:
                presence = presences[user.id]
                target = presence / presences_sum * counts_sum
            elif counts[user.id]:
                presence = None
                target = None
            else:
                continue

            rows.append(
                {
                    "user": user,
                    "presence": presence,
                    "target": round(target, 1) if target else None,
                    "handled": counts[user.id],
                    "reached": (
                        round(100 * counts[user.id] / target) if target else None
                    ),
                }
            )

        return {
            "year": year,
            "users": sorted(
                rows,
                key=lambda row: (
                    row["handled"],
                    -1e9 if row["reached"] is None else -row["reached"]
                ),
                reverse=True,
            ),
        }


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
        related_name="days",
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
        parts = [local_date_format(self.day, "D d.m.Y")]
        if self.handled_by:
            parts.append("({})".format(self.handled_by))
        return " ".join(parts)

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
                    self.day >= today and not self.handled_by and "text-danger",
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
        unique_together = [("app", "user", "year")]
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

    def _affected(self):
        return Day.objects.filter(
            Q(app=self.app),
            Q(day__week_day=(self.day_of_week + 1) % 7 + 1),
            Q(day__gte=date.today()),
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._affected().filter(handled_by=None).update(handled_by=self.user)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._affected().filter(handled_by=self.user).update(handled_by=None)

    save.alters_data = True
    delete.alters_data = True


def on_user_saved(sender, instance, created, **kwargs):
    if created:
        if "feinheit" in instance.email:
            instance.apps.set(App.objects.all())
        else:
            instance.apps.set(App.objects.filter(slug="kochen"))

    elif not instance.is_active:
        Day.objects.filter(handled_by=instance, day__gte=date.today()).update(
            handled_by=None
        )


signals.post_save.connect(on_user_saved, sender=User)


class PublicHoliday(models.Model):
    name = models.CharField(_("name"), max_length=100)
    day = models.DateField(_("day"), unique=True)

    class Meta:
        verbose_name = _("public holiday")
        verbose_name_plural = _("public holidays")

    def __str__(self):
        return "{} ({})".format(self.name, self.day)


class CompanyHoliday(models.Model):
    date_from = models.DateField(_("date from"))
    date_until = models.DateField(_("date until"))

    class Meta:
        verbose_name = _("company holiday")
        verbose_name_plural = _("company holidays")

    def __str__(self):
        return "{} - {}".format(self.date_from, self.date_until)

    def contains(self, day):
        return self.date_from <= day <= self.date_until
