from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.tools.formats import local_date_format
from workbench.tools.models import SearchQuerySet, Model, MoneyField
from workbench.tools.urls import model_urls


class Stage(Model):
    title = models.CharField(_("title"), max_length=200)
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("stage")
        verbose_name_plural = _("stages")

    def __str__(self):
        return self.title


class DealQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(closed_at__isnull=True)


@model_urls()
class Deal(Model):
    OPEN = 10
    ACCEPTED = 20
    DECLINED = 30

    STATUS_CHOICES = (
        (OPEN, _("open")),
        (ACCEPTED, _("accepted")),
        (DECLINED, _("declined")),
    )

    customer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        verbose_name=_("customer"),
        related_name="+",
    )
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("contact"),
        related_name="+",
    )

    stage = models.ForeignKey(
        Stage, on_delete=models.PROTECT, verbose_name=_("stage"), related_name="deals"
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("owned by"), related_name="+"
    )
    estimated_value = MoneyField(_("estimated value"), default=None)

    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=OPEN
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    closed_at = models.DateTimeField(_("closed at"), blank=True, null=True)

    objects = models.Manager.from_queryset(DealQuerySet)()

    class Meta:
        verbose_name = _("deal")
        verbose_name_plural = _("deals")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.OPEN:
            self.closed_at = None
        elif not self.closed_at:
            self.closed_at = timezone.now()
        super().save(*args, **kwargs)

    save.alters_data = True

    def pretty_status(self):
        d = {
            "created_at": local_date_format(self.created_at, "d.m.Y"),
            "closed_at": self.closed_at and local_date_format(self.closed_at, "d.m.Y"),
            "status": self.get_status_display(),
        }

        if self.status == self.OPEN:
            return _("Open since %(created_at)s") % d
        return _("%(status)s on %(closed_at)s") % d
