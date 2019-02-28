from decimal import Decimal

from django.contrib import messages
from django.db import models
from django.db.models import Max, Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _, ugettext

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.services.models import ServiceType
from workbench.tools.models import SearchQuerySet, Model, MoneyField, HoursField
from workbench.tools.urls import model_urls


class ProjectQuerySet(SearchQuerySet):
    pass


@model_urls()
class Project(Model):
    ACQUISITION = 10
    WORK_IN_PROGRESS = 20
    FINISHED = 30
    DECLINED = 40

    STATUS_CHOICES = (
        (ACQUISITION, _("Acquisition")),
        (WORK_IN_PROGRESS, _("Work in progress")),
        (FINISHED, _("Finished")),
        (DECLINED, _("Declined")),
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

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("owned by"), related_name="+"
    )

    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=ACQUISITION
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    invoicing = models.BooleanField(
        _("invoicing"),
        default=True,
        help_text=_("This project is eligible for invoicing."),
    )
    maintenance = models.BooleanField(
        _("maintenance"),
        default=False,
        help_text=_("This project is used for maintenance work."),
    )

    _code = models.IntegerField(_("code"))

    objects = models.Manager.from_queryset(ProjectQuerySet)()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("project")
        verbose_name_plural = _("projects")

    def __str__(self):
        return "%s %s %s" % (self.code, self.title, self.owned_by.get_short_name())

    def __html__(self):
        return format_html(
            "<small>{}</small> {} - {}",
            self.code,
            self.title,
            self.owned_by.get_short_name(),
        )

    @property
    def code(self):
        return "%s-%04d" % (self.created_at.year, self._code)

    def save(self, *args, **kwargs):
        if not self.pk:
            self._code = RawSQL(
                "SELECT COALESCE(MAX(_code), 0) + 1 FROM projects_project"
                " WHERE EXTRACT(year FROM created_at) = %s",
                (timezone.now().year,),
            )
        super().save(*args, **kwargs)

    save.alters_data = True

    def status_css(self):
        return {
            self.ACQUISITION: "info",
            self.WORK_IN_PROGRESS: "success",
            self.FINISHED: "default",
            self.DECLINED: "warning",
        }[self.status]

    @cached_property
    def overview(self):
        # Avoid circular imports
        from workbench.logbook.models import LoggedHours

        return {
            "logged": LoggedHours.objects.filter(service__project=self)
            .order_by()
            .aggregate(h=Sum("hours"))["h"]
            or Decimal(),
            "effort": sum(
                (service.effort_hours for service in self.services.all()), Decimal()
            ),
        }

    def pretty_status(self):
        parts = [self.get_status_display()]
        if not self.invoicing:
            parts.append(ugettext("no invoicing"))
        if self.maintenance:
            parts.append(ugettext("maintenance"))
        return ", ".join(parts)


@model_urls()
class Service(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("project"),
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("offer"),
        blank=True,
        null=True,
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    position = models.PositiveIntegerField(_("position"), default=0)

    effort_hours = HoursField(_("effort hours"), default=0)
    cost = MoneyField(_("cost"), default=0)

    class Meta:
        ordering = ("position", "created_at")
        verbose_name = _("service")
        verbose_name_plural = _("services")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.position:
            max_pos = self.__class__._default_manager.aggregate(m=Max("position"))["m"]
            self.position = 10 + (max_pos or 0)
        if self.pk:
            efforts = self.efforts.all()
            self.effort_hours = sum((e.hours for e in efforts), Decimal())
            self.cost += sum((e.cost for e in efforts), Decimal())
            self.cost += sum((c.cost for c in self.costs.all()), Decimal())
        super().save(*args, **kwargs)

    @classmethod
    def allow_update(cls, instance, request):
        if instance.offer and instance.offer.status > instance.offer.IN_PREPARATION:
            messages.error(
                request,
                _(
                    "Cannot modify a service bound to an offer"
                    " which is not in preparation anymore."
                ),
            )
            return False
        return True

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.offer and instance.offer.status > instance.offer.IN_PREPARATION:
            messages.error(
                request,
                _(
                    "Cannot modify a service bound to an offer"
                    " which is not in preparation anymore."
                ),
            )
            return False
        return super().allow_delete(instance, request)


class Effort(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="efforts",
        verbose_name=_("service"),
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT,
        verbose_name=_("service type"),
        related_name="+",
    )
    hours = HoursField(_("hours"))

    class Meta:
        ordering = ("service_type",)
        unique_together = (("service", "service_type"),)
        verbose_name = _("effort")
        verbose_name_plural = _("efforts")

    def __str__(self):
        return "%s" % self.service_type

    @property
    def urls(self):
        return self.service.urls

    def get_absolute_url(self):
        return self.service.get_absolute_url()

    @property
    def cost(self):
        return self.service_type.billing_per_hour * self.hours


class Cost(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="costs",
        verbose_name=_("service"),
    )
    title = models.CharField(_("title"), max_length=200)
    cost = MoneyField(_("cost"), default=None)
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "pk")
        verbose_name = _("cost")
        verbose_name_plural = _("costs")

    def __str__(self):
        return self.title

    @property
    def urls(self):
        return self.service.urls

    def get_absolute_url(self):
        return self.service.get_absolute_url()
