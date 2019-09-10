from collections import defaultdict
from decimal import Decimal

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

    def orders(self):
        return self.filter(type=Project.ORDER)

    def without_invoices(self):
        from workbench.invoices.models import Invoice

        return self.exclude(
            id__in=Invoice.objects.valid()
            .filter(project__isnull=False)
            .values("project")
        )

    def with_accepted_offers(self):
        from workbench.offers.models import Offer

        return self.filter(id__in=Offer.objects.accepted().values("project"))


@model_urls
class Project(Model):
    ORDER = "order"
    MAINTENANCE = "maintenance"
    INTERNAL = "internal"

    TYPE_CHOICES = [
        (ORDER, _("Order")),
        (MAINTENANCE, _("Maintenance")),
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
        User, on_delete=models.PROTECT, verbose_name=_("responsible"), related_name="+"
    )

    type = models.CharField(_("type"), choices=TYPE_CHOICES, max_length=20)
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    closed_on = models.DateField(_("closed on"), blank=True, null=True)

    _code = models.IntegerField(_("code"))
    _fts = models.TextField(editable=False, blank=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("project")
        verbose_name_plural = _("projects")

    def __str__(self):
        return "%s %s - %s" % (self.code, self.title, self.owned_by.get_short_name())

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
        new = not self.pk
        if new:
            self._code = RawSQL(
                "SELECT COALESCE(MAX(_code), 0) + 1 FROM projects_project"
                " WHERE EXTRACT(year FROM created_at) = %s",
                (timezone.now().year,),
            )
            super().save(*args, **kwargs)
            self.refresh_from_db()

        self._fts = " ".join(
            str(part)
            for part in [
                self.code,
                self.customer.name,
                self.contact.full_name if self.contact else "",
            ]
        )
        if new:
            super().save()
        else:
            super().save(*args, **kwargs)

    save.alters_data = True

    @property
    def status_badge(self):
        css = {
            self.MAINTENANCE: "secondary",
            self.ORDER: "success",
            self.INTERNAL: "warning",
        }[self.type]

        if self.closed_on:
            css = "light"
        return format_html(
            '<span class="badge badge-{}">{}</span>', css, self.pretty_status
        )

    @property
    def pretty_status(self):
        parts = [str(self.get_type_display())]
        if self.closed_on:
            parts.append(gettext("closed on %s") % local_date_format(self.closed_on))
        return ", ".join(parts)

    @cached_property
    def grouped_services(self):
        # Avoid circular imports
        from workbench.logbook.models import LoggedHours, LoggedCost

        # Logged vs. service hours
        service_hours = Z
        logged_hours = Z
        # Logged vs. service cost
        service_cost = Z
        logged_cost = Z
        # Project logbook vs. project service cost (hours and cost)
        total_service_cost = Z
        total_logged_cost = Z
        total_service_hours_rate_undefined = Z
        total_logged_hours_rate_undefined = Z

        offers = {
            offer.pk: (offer, []) for offer in self.offers.select_related("owned_by")
        }
        offers[None] = (None, [])

        logged_hours_per_service_and_user = defaultdict(dict)
        logged_hours_per_user = defaultdict(lambda: Z)
        logged_hours_per_effort_rate = defaultdict(lambda: Z)

        for row in (
            LoggedHours.objects.order_by()
            .filter(service__project=self)
            .values("service", "rendered_by")
            .annotate(Sum("hours"))
        ):
            logged_hours_per_user[row["rendered_by"]] += row["hours__sum"]
            logged_hours_per_service_and_user[row["service"]][row["rendered_by"]] = row[
                "hours__sum"
            ]

        logged_cost_per_service = {
            row["service"]: row["cost__sum"]
            for row in LoggedCost.objects.order_by()
            .filter(project=self)
            .values("service")
            .annotate(Sum("cost"))
        }

        not_archived_logged_hours_per_service = {
            row["service"]: row["hours__sum"]
            for row in LoggedHours.objects.order_by()
            .filter(
                service__project=self,
                archived_at__isnull=True,
                service__effort_rate__isnull=False,
            )
            .values("service")
            .annotate(Sum("hours"))
        }
        not_archived_logged_cost_per_service = {
            row["service"]: row["cost__sum"]
            for row in LoggedCost.objects.order_by()
            .filter(project=self, archived_at__isnull=False)
            .values("service")
            .annotate(Sum("cost"))
        }

        users = {
            user.id: user
            for user in User.objects.filter(id__in=logged_hours_per_user.keys())
        }

        for service in self.services.all():
            logged = logged_hours_per_service_and_user.get(service.id, {})
            row = {
                "service": service,
                "logged_hours": sum(logged.values(), Z),
                "logged_hours_per_user": sorted(
                    ((users[user], hours) for user, hours in logged.items()),
                    key=lambda row: row[1],
                    reverse=True,
                ),
                "logged_cost": logged_cost_per_service.get(service.id, Z),
                "not_archived_logged_hours": not_archived_logged_hours_per_service.get(
                    service.id, Z
                ),
                "not_archived_logged_cost": not_archived_logged_cost_per_service.get(
                    service.id, Z
                ),
            }
            row["not_archived"] = (service.effort_rate or Z) * row[
                "not_archived_logged_hours"
            ] + row["not_archived_logged_cost"]

            logged_hours += row["logged_hours"]
            logged_cost += row["logged_cost"]
            total_logged_cost += row["logged_cost"]
            logged_hours_per_effort_rate[service.effort_rate] += row["logged_hours"]

            if not service.is_rejected:
                service_hours += service.service_hours
                service_cost += service.cost or Z
                total_service_cost += service.service_cost

            if service.effort_rate is not None:
                total_logged_cost += service.effort_rate * row["logged_hours"]
            else:
                total_logged_hours_rate_undefined += row["logged_hours"]
                if not service.is_rejected:
                    total_service_hours_rate_undefined += service.service_hours

            offers[service.offer_id][1].append(row)

        if None in logged_cost_per_service:
            offers[None][1].append(
                {
                    "service": Service(
                        title=gettext("Not bound to a particular service."),
                        service_cost=Z,
                    ),
                    "logged_hours": Z,
                    "logged_cost": logged_cost_per_service[None],
                }
            )

            logged_cost += logged_cost_per_service[None]
            total_logged_cost += logged_cost_per_service[None]

        return {
            "offers": sorted(
                (
                    value
                    for value in offers.values()
                    if value[1] or value[0] is not None
                ),
                key=lambda item: (
                    # Rejected offers are at the end
                    item[0].is_rejected if item[0] else False,
                    # None is between rejected offers and other offers
                    item[0] is None,
                    # Else order by code
                    item[0]._code if item[0] else 1e100,
                ),
            ),
            "logged_hours": logged_hours,
            "logged_hours_per_user": sorted(
                ((users[user], hours) for user, hours in logged_hours_per_user.items()),
                key=lambda row: row[1],
                reverse=True,
            ),
            "logged_hours_per_effort_rate": sorted(
                (
                    (rate, hours)
                    for rate, hours in logged_hours_per_effort_rate.items()
                    if hours
                ),
                key=lambda row: row[0] or Decimal("9999999"),
                reverse=True,
            ),
            "logged_cost": logged_cost,
            "service_hours": service_hours,
            "service_cost": service_cost,
            "total_service_cost": total_service_cost,
            "total_logged_cost": total_logged_cost,
            "total_service_hours_rate_undefined": total_service_hours_rate_undefined,
            "total_logged_hours_rate_undefined": total_logged_hours_rate_undefined,
        }

    @cached_property
    def project_invoices(self):
        return self.invoices.select_related("contact__organization").reverse()

    @cached_property
    def project_invoices_total_excl_tax(self):
        return sum((invoice.total_excl_tax for invoice in self.project_invoices), Z)

    @cached_property
    def not_archived_total(self):
        # Avoid circular imports
        from workbench.logbook.models import LoggedHours

        total = Z
        hours_rate_undefined = Z

        for row in (
            LoggedHours.objects.order_by()
            .filter(service__project=self, archived_at__isnull=True)
            .values("service__effort_rate")
            .annotate(Sum("hours"))
        ):
            if row["service__effort_rate"] is None:
                hours_rate_undefined += row["hours__sum"]
            else:
                total += row["hours__sum"] * row["service__effort_rate"]

        total += self.loggedcosts.order_by().aggregate(Sum("cost"))["cost__sum"] or Z
        return {"total": total, "hours_rate_undefined": hours_rate_undefined}


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
    allow_logging = models.BooleanField(
        _("allow logging"),
        default=True,
        help_text=_(
            "Deactivate this for service entries which are only used for budgeting."
        ),
    )
    is_optional = models.BooleanField(
        _("is optional"),
        default=False,
        help_text=_("Optional services to not count towards the offer total."),
    )
    role = models.ForeignKey(
        "circles.Role",
        on_delete=models.SET_NULL,
        related_name="services",
        verbose_name=_("role"),
        blank=True,
        null=True,
    )

    def get_absolute_url(self):
        return self.project.get_absolute_url()

    @classmethod
    def allow_update(cls, instance, request):
        return True

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.offer and instance.offer.status > instance.offer.IN_PREPARATION:
            messages.error(
                request,
                _(
                    "Cannot delete a service bound to an offer"
                    " which is not in preparation anymore."
                ),
            )
            return False
        return super().allow_delete(instance, request)

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return instance.get_absolute_url() if instance else "projects_project_list"

    @property
    def is_rejected(self):
        return self.offer.is_rejected if self.offer else False
