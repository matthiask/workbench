from datetime import date

from django.contrib import messages
from django.db import models
from django.db.models import Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.services.models import ServiceBase
from workbench.tools.formats import local_date_format
from workbench.tools.models import Model, SearchQuerySet, Z
from workbench.tools.urls import model_urls


class ProjectQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(closed_on__isnull=True)


@model_urls
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

    objects = ProjectQuerySet.as_manager()

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

    @property
    def status_css(self):
        if self.closed_on:
            return "secondary"

        return {
            self.ACQUISITION: "info",
            self.MAINTENANCE: "info",
            self.ORDER: "success",
            self.INTERNAL: "warning",
        }[self.type]

    @property
    def pretty_status(self):
        parts = [str(self.get_type_display())]
        if self.closed_on:
            parts.append(
                gettext("closed on %s") % local_date_format(self.closed_on, "d.m.Y")
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
            "effort": sum(
                (service.service_hours for service in self.services.all()), Z
            ),
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

        for service in self.services.select_related("offer__project"):
            service.logged_hours = logged_hours_per_service.get(service.id, 0)
            service.logged_cost = logged_cost_per_service.get(service.id, 0)

            if service.offer not in offers:
                offers[service.offer] = []
            offers[service.offer].append(service)

        if None in logged_cost_per_service:
            s = Service(
                title=gettext("Not bound to a particular service."), service_cost=Z
            )
            s.logged_hours = Z
            s.logged_cost = logged_cost_per_service[None]
            offers.setdefault(None, []).append(s)

        return sorted(
            offers.items(),
            key=lambda item: (
                item[0] and item[0].offered_on or date.max,
                item[0] and item[0].pk or 1e100,
            ),
        )

    @cached_property
    def project_invoices(self):
        return self.invoices.select_related("contact__organization")


@model_urls
class Service(ServiceBase):
    RELATED_MODEL_FIELD = "offer"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("project"),
    )
    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.SET_NULL,
        related_name="services",
        verbose_name=_("offer"),
        blank=True,
        null=True,
    )

    def get_absolute_url(self):
        return self.project.get_absolute_url()

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

    allow_delete = allow_update

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax() and "/move/" not in request.path:  # XXX ugly
            return instance.get_absolute_url() if instance else "projects_project_list"
