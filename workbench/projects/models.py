from collections import defaultdict
from datetime import date
from itertools import chain

from django.contrib import messages
from django.db import models
from django.db.models import Max, Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.translation import ugettext_lazy as _, ugettext

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.services.models import ServiceType
from workbench.tools.formats import local_date_format
from workbench.tools.models import SearchQuerySet, Model, MoneyField, HoursField, Z
from workbench.tools.urls import model_urls


class ProjectQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(closed_on__isnull=True)


@model_urls()
class Project(Model):
    ACQUISITION = "acquisition"
    MAINTENANCE = "maintenance"
    ORDER = "order"
    INTERNAL = "internal"

    TYPE_CHOICES = [
        (ACQUISITION, _("Acquisition")),
        (MAINTENANCE, _("Maintenance")),
        (ORDER, _("Order")),
        (INTERNAL, _("Internal")),
    ]

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

    type = models.CharField(_("type"), choices=TYPE_CHOICES, max_length=20)
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    closed_on = models.DateField(_("closed on"), blank=True, null=True)

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
        new = False
        if not self.pk:
            self._code = RawSQL(
                "SELECT COALESCE(MAX(_code), 0) + 1 FROM projects_project"
                " WHERE EXTRACT(year FROM created_at) = %s",
                (timezone.now().year,),
            )
            new = True
        super().save(*args, **kwargs)
        if new:
            self.refresh_from_db()

    save.alters_data = True

    def status_css(self):
        if self.closed_on:
            return "secondary"

        return {
            self.ACQUISITION: "info",
            self.MAINTENANCE: "info",
            self.ORDER: "success",
            self.INTERNAL: "warning",
        }[self.type]

    def pretty_status(self):
        parts = [self.get_type_display()]
        if self.closed_on:
            parts.append(
                ugettext("closed on %s") % local_date_format(self.closed_on, "d.m.Y")
            )
        return ", ".join(parts)

    @cached_property
    def overview(self):
        # Avoid circular imports
        from workbench.logbook.models import LoggedHours

        return {
            "logged": LoggedHours.objects.filter(service__project=self)
            .order_by()
            .aggregate(h=Sum("hours"))["h"]
            or Z,
            "effort": sum((service.effort_hours for service in self.services.all()), Z),
        }

    @cached_property
    def grouped_services(self):
        # Avoid circular imports
        from workbench.logbook.models import LoggedHours, LoggedCost

        offers = {}
        logged_hours_per_service = {
            row["service"]: row["hours__sum"]
            for row in LoggedHours.objects.order_by()
            .filter(service__project=self)
            .values("service")
            .annotate(Sum("hours"))
        }
        logged_cost_per_service = {
            row["service"]: row["cost__sum"]
            for row in LoggedCost.objects.order_by()
            .filter(project=self)
            .values("service")
            .annotate(Sum("cost"))
        }

        for service in self.services.select_related("offer").prefetch_related(
            "efforts", "costs"
        ):
            service.logged_hours = logged_hours_per_service.get(service.id, 0)
            service.logged_cost = logged_cost_per_service.get(service.id, 0)
            service.planned_cost = sum((cost.cost for cost in service.costs.all()), 0)

            if service.offer not in offers:
                offers[service.offer] = []
            offers[service.offer].append(service)

        if None in logged_cost_per_service:
            s = Service(title=_("Not bound to a particular service."))
            s.logged_cost = logged_cost_per_service[None]
            s.planned_cost = Z
            offers.setdefault(None, []).append(s)

        return sorted(
            offers.items(),
            key=lambda item: (
                item[0] and item[0].offered_on or date.max,
                item[0] and item[0].pk or 1e100,
            ),
        )


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
        on_delete=models.SET_NULL,
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

    objects = ServiceQuerySet.as_manager()

    class Meta:
        ordering = ("position", "created_at")
        verbose_name = _("service")
        verbose_name_plural = _("services")

    def __str__(self):
        return " - ".join(
            filter(None, (self.title, Truncator(self.description).chars(50)))
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_offer = self.offer_id

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

        # Circular imports
        from workbench.offers.models import Offer

        ids = filter(None, [self._orig_offer, self.offer_id])
        for offer in Offer.objects.filter(id__in=ids):
            offer.save()

    save.alters_data = True

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        if self._orig_offer:
            # Circular imports
            from workbench.offers.models import Offer

            ids = filter(None, [self._orig_offer, self.offer_id])
            for offer in Offer.objects.filter(id__in=ids):
                offer.save()

    delete.alters_data = True

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


class Cost(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="costs",
        verbose_name=_("service"),
    )
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
