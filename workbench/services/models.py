from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from workbench.tools.formats import Z1, Z2
from workbench.tools.models import HoursFieldAllowNegatives, Model, MoneyField
from workbench.tools.validation import raise_if_errors


class ServiceType(Model):
    title = models.CharField(_("title"), max_length=40)
    hourly_rate = MoneyField(_("hourly rate"))
    position = models.IntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("service type")
        verbose_name_plural = _("service types")

    def __str__(self):
        return self.title


class ServiceBase(Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    position = models.IntegerField(_("position"), default=0)

    service_hours = HoursFieldAllowNegatives(_("service hours"), default=0)
    service_cost = MoneyField(_("service cost"), default=0)

    effort_type = models.CharField(_("effort type"), max_length=50, blank=True)
    effort_hours = HoursFieldAllowNegatives(_("hours"), blank=True, null=True)
    effort_rate = MoneyField(_("hourly rate"), blank=True, null=True)

    cost = MoneyField(_("cost"), blank=True, null=True)
    third_party_costs = MoneyField(
        _("third party costs"),
        default=None,
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )

    class Meta:
        abstract = True
        ordering = ["position", "created_at"]
        verbose_name = _("service")
        verbose_name_plural = _("services")

    def __str__(self):
        return Truncator(": ".join(filter(None, (self.title, self.description)))).chars(
            100
        )

    def project_service_title(self):
        title = "{}: {}{}{}".format(
            self.project,
            self.title,
            ": " if self.description else "",
            self.description,
        )
        return Truncator(title).chars(100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._related_model = self._meta.get_field(self.RELATED_MODEL_FIELD)
        self._orig_related_id = getattr(self, self._related_model.attname)

    def save(self, *args, **kwargs):
        skip_related_model = kwargs.pop("skip_related_model", False)

        if not self.position:
            max_pos = self.__class__._default_manager.aggregate(m=Max("position"))["m"]
            self.position = 10 + (max_pos or 0)
        self.service_hours = self.effort_hours or Z1
        self.service_cost = self.cost or Z2
        if all((self.effort_hours, self.effort_rate)):
            self.service_cost += self.effort_hours * self.effort_rate

        super().save(*args, **kwargs)

        if not skip_related_model:
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

    def clean_fields(self, exclude):
        super().clean_fields(exclude)
        errors = {}
        effort = (self.effort_type != "", self.effort_rate is not None)
        if any(effort) and not all(effort):
            if self.effort_type == "":
                errors["effort_type"] = _("Either fill in all fields or none.")
            if self.effort_rate is None:
                errors["effort_rate"] = _("Either fill in all fields or none.")
        if self.third_party_costs is not None and self.cost is None:
            errors["cost"] = _("Cannot be empty if third party costs is set.")
        raise_if_errors(errors, exclude)
