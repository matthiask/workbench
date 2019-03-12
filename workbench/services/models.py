from collections import defaultdict
from datetime import date

from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from workbench.tools.models import Model, MoneyField, HoursField, Z
from workbench.tools.validation import raise_if_errors


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

    service_hours = HoursField(_("service hours"), default=0)
    service_cost = MoneyField(_("service cost"), default=0)

    effort_type = models.CharField(_("effort type"), max_length=50, blank=True)
    effort_hours = HoursField(_("hours"), blank=True, null=True)
    effort_rate = MoneyField(_("hourly rate"), blank=True, null=True)

    cost = MoneyField(_("cost"), blank=True, null=True)
    third_party_costs = MoneyField(
        _("third party costs"),
        default=None,
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )

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
            self.service_hours = self.effort_hours or Z
            self.service_cost = self.cost or Z
            if all((self.effort_hours, self.effort_rate)):
                self.service_cost += self.effort_hours * self.effort_rate
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

    def clean_fields(self, exclude):
        super().clean_fields(exclude)
        errors = {}
        effort = (self.effort_type, self.effort_rate)
        if any(effort) and not all(effort):
            if not self.effort_type:
                errors["effort_type"] = _("Either fill in all fields or none.")
            if not self.effort_rate:
                errors["effort_rate"] = _("Either fill in all fields or none.")
        if self.third_party_costs is not None and self.cost is None:
            errors["cost"] = _("Cannot be empty if third party costs is set.")
        raise_if_errors(errors, exclude)
