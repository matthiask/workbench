from collections import defaultdict
from datetime import date
from itertools import chain

from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.translation import ugettext_lazy as _

from workbench.tools.models import Model, MoneyField, HoursField, Z


class ServiceType(Model):
    title = models.CharField(_("title"), max_length=40)
    billing_per_hour = MoneyField(_("billing per hour"))
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("service type")
        verbose_name_plural = _("service types")

    def __str__(self):
        return self.title


class ServiceQuerySet(models.QuerySet):
    def choices(self):
        offers = defaultdict(list)
        for service in self.select_related("offer"):
            offers[service.offer].append((service.id, str(service)))
        return [("", "----------")] + [
            (offer or _("Not offered yet"), services)
            for offer, services in sorted(
                offers.items(),
                key=lambda item: (
                    item[0] and item[0].offered_on or date.max,
                    item[0] and item[0].pk or 1e100,
                ),
            )
        ]


class ServiceBase(Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    position = models.PositiveIntegerField(_("position"), default=0)

    effort_hours = HoursField(_("effort hours"), default=0)
    cost = MoneyField(_("cost"), default=0)

    objects = ServiceQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["position", "created_at"]
        verbose_name = _("service")
        verbose_name_plural = _("services")

    def __str__(self):
        return " - ".join(
            filter(None, (self.title, Truncator(self.description).chars(50)))
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._related_model = self._meta.get_field(self.RELATED_MODEL_FIELD)
        self._orig_related_id = getattr(self, self._related_model.attname)

    def get_absolute_url(self):
        return self.project.urls.url("services")

    def save(self, *args, **kwargs):
        if not self.position:
            max_pos = self.__class__._default_manager.aggregate(m=Max("position"))["m"]
            self.position = 10 + (max_pos or 0)
        if self.pk:
            efforts = self.efforts.all()
            self.effort_hours = sum((e.hours for e in efforts), Z)
            self.cost = sum((i.cost for i in chain(efforts, self.costs.all())), 0)
        super().save(*args, **kwargs)

        ids = filter(
            None, [self._orig_related_id, getattr(self, self._related_model.attname)]
        )
        for instance in self._related_model.remote_field.model._default_manager.filter(
            id__in=ids
        ):
            instance.save()

    save.alters_data = True

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        if self._orig_related_id:
            ids = filter(
                None,
                [self._orig_related_id, getattr(self, self._related_model.attname)],
            )
            for (
                instance
            ) in self._related_model.remote_field.model._default_manager.filter(
                id__in=ids
            ):
                instance.save()

    delete.alters_data = True

    @classmethod
    def allow_update(cls, instance, request):
        raise NotImplementedError

    @classmethod
    def allow_delete(cls, instance, request):
        raise NotImplementedError


class EffortBase(Model):
    title = models.CharField(_("title"), max_length=200)
    billing_per_hour = MoneyField(_("billing per hour"), default=None)
    hours = HoursField(_("hours"))
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.SET_NULL,
        verbose_name=_("service type"),
        related_name="+",
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True
        ordering = ["pk"]
        verbose_name = _("effort")
        verbose_name_plural = _("efforts")

    def __str__(self):
        return "%s" % self.title

    @property
    def urls(self):
        return self.service.urls

    def get_absolute_url(self):
        return self.service.get_absolute_url()

    @property
    def cost(self):
        return self.billing_per_hour * self.hours


class CostBase(Model):
    title = models.CharField(_("title"), max_length=200)
    cost = MoneyField(_("cost"), default=None)
    third_party_costs = MoneyField(
        _("third party costs"),
        default=None,
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )

    class Meta:
        abstract = True
        ordering = ["pk"]
        verbose_name = _("cost")
        verbose_name_plural = _("costs")

    def __str__(self):
        return self.title

    @property
    def urls(self):
        return self.service.urls

    def get_absolute_url(self):
        return self.service.get_absolute_url()
