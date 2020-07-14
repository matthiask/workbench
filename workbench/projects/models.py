import datetime as dt
from collections import defaultdict
from decimal import Decimal
from functools import total_ordering

from django.contrib import messages
from django.db import models
from django.db.models import F, Prefetch, Q, Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.services.models import ServiceBase
from workbench.tools.formats import Z1, Z2, local_date_format
from workbench.tools.models import Model, MoneyField, SearchQuerySet
from workbench.tools.urls import model_urls
from workbench.tools.validation import in_days, raise_if_errors


class CampaignQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(
            Q(
                id__in=Project.objects.open()
                .filter(campaign__isnull=False)
                .values("campaign")
            )
        )

    def closed(self):
        return self.filter(
            ~Q(
                id__in=Project.objects.open()
                .filter(campaign__isnull=False)
                .values("campaign")
            )
        )


@model_urls
class Campaign(Model):
    customer = models.ForeignKey(
        Organization, on_delete=models.PROTECT, verbose_name=_("customer")
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("responsible")
    )
    _fts = models.TextField(editable=False, blank=True)

    objects = CampaignQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]
        verbose_name = _("campaign")
        verbose_name_plural = _("campaigns")

    def __str__(self):
        return "%s %s - %s" % (self.code, self.title, self.owned_by.get_short_name())

    def __html__(self):
        return format_html(
            "<small>{}</small> {} - {}",
            self.code,
            self.title,
            self.owned_by.get_short_name(),
        )

    def save(self, *args, **kwargs):
        self._fts = " ".join(str(part) for part in [self.code, self.customer.name])
        super().save(*args, **kwargs)

    save.alters_data = True

    @classmethod
    def allow_delete(cls, instance, request):
        return None

    @cached_property
    def statistics(self):
        from workbench.reporting.project_budget_statistics import (
            project_budget_statistics,
        )

        pbs = project_budget_statistics(self.projects.all())
        overall = pbs["overall"]
        overall["gross_margin_per_hour"] = (
            (overall["invoiced"] - overall["third_party_costs"]) / overall["hours"]
            if overall["hours"]
            else None
        )
        pbs["statistics"] = sorted(pbs["statistics"], key=lambda s: s["project"])
        return pbs


class ProjectQuerySet(SearchQuerySet):
    def open(self, *, on=None):
        return (
            self.filter(closed_on__isnull=True)
            if on is None
            else self.filter(
                Q(closed_on__isnull=True) | Q(closed_on__gt=on),
                created_at__lte=timezone.make_aware(
                    dt.datetime.combine(on, dt.time.max)
                ),
            )
        )

    def closed(self):
        return self.filter(closed_on__isnull=False)

    def orders(self):
        return self.filter(type=Project.ORDER)

    def without_invoices(self):
        from workbench.invoices.models import Invoice

        return self.exclude(
            id__in=Invoice.objects.invoiced()
            .filter(project__isnull=False)
            .values("project")
        )

    def with_accepted_offers(self):
        from workbench.offers.models import Offer

        return self.filter(id__in=Offer.objects.accepted().values("project"))

    def solely_declined_offers(self):
        from workbench.offers.models import Offer

        return self.filter(
            Q(id__in=Offer.objects.values("project"))
            & ~Q(
                id__in=Offer.objects.filter(
                    status__in=(Offer.IN_PREPARATION, Offer.OFFERED, Offer.ACCEPTED)
                ).values("project")
            )
        )

    def old_projects(self):
        from workbench.logbook.models import LoggedHours

        return (
            self.open()
            .filter(id__in=LoggedHours.objects.order_by().values("service__project"))
            .exclude(
                id__in=LoggedHours.objects.order_by()
                .filter(rendered_on__gte=in_days(-60))
                .values("service__project")
            )
        )

    def invalid_customer_contact_combination(self):
        return self.exclude(customer=F("contact__organization"))


@model_urls
@total_ordering
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
        Organization, on_delete=models.PROTECT, verbose_name=_("customer")
    )
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("contact"),
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(
        _("project description"),
        blank=True,
        help_text=_(
            "Do not use this for the offer description."
            " You can add the offer description later."
        ),
    )
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("responsible")
    )

    type = models.CharField(_("type"), choices=TYPE_CHOICES, max_length=20)
    flat_rate = MoneyField(
        _("flat rate"),
        blank=True,
        null=True,
        help_text=_("Set this if you want all services to have the same hourly rate."),
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    closed_on = models.DateField(_("closed on"), blank=True, null=True)

    _code = models.IntegerField(_("code"))
    _fts = models.TextField(editable=False, blank=True)

    cost_center = models.ForeignKey(
        "reporting.CostCenter",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("cost center"),
        related_name="projects",
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("campaign"),
        related_name="projects",
    )

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

    def __lt__(self, other):
        return self.id < other.id if isinstance(other, Project) else 1

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

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}
        if self.closed_on and self.closed_on > dt.date.today():
            errors["closed_on"] = _(
                "Leave this empty if you do not want to close the project yet."
            )
        raise_if_errors(errors)

    @property
    def status_badge(self):
        css = {
            self.MAINTENANCE: "secondary",
            self.ORDER: "success",
            self.INTERNAL: "info",
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
        from workbench.deals.models import Deal
        from workbench.logbook.models import LoggedCost, LoggedHours

        # Logged vs. service hours
        service_hours = defaultdict(lambda: Z1)
        logged_hours = defaultdict(lambda: Z1)
        # Logged vs. service cost
        service_cost = defaultdict(lambda: Z2)
        logged_cost = defaultdict(lambda: Z2)
        # Project logbook vs. project service cost (hours and cost)
        total_service_cost = Z2
        total_logged_cost = Z2
        total_service_hours_rate_undefined = Z1
        total_logged_hours_rate_undefined = Z1

        offers = self.offers.select_related("owned_by").prefetch_related(
            Prefetch("deals", Deal.objects.select_related("owned_by"))
        )
        offers_map = {offer.id: offer for offer in offers}
        services_by_offer = defaultdict(
            lambda: {"services": []}, ((offer, {"services": []}) for offer in offers)
        )

        logged_hours_per_service_and_user = defaultdict(dict)
        logged_hours_per_user = defaultdict(lambda: Z1)
        logged_hours_per_effort_rate = defaultdict(lambda: Z1)

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
            .filter(service__project=self)
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
            .filter(service__project=self, archived_at__isnull=True)
            .values("service")
            .annotate(Sum("cost"))
        }

        users = {
            user.id: user
            for user in User.objects.filter(id__in=logged_hours_per_user.keys())
        }

        for service in self.services.all():
            service.offer = offers_map.get(service.offer_id)  # Reuse
            logged = logged_hours_per_service_and_user.get(service.id, {})
            row = {
                "service": service,
                "logged_hours": sum(logged.values(), Z1),
                "logged_hours_per_user": sorted(
                    ((users[user], hours) for user, hours in logged.items()),
                    key=lambda row: row[1],
                    reverse=True,
                ),
                "logged_cost": logged_cost_per_service.get(service.id, Z2),
                "not_archived_logged_hours": not_archived_logged_hours_per_service.get(
                    service.id, Z1
                ),
                "not_archived_logged_cost": not_archived_logged_cost_per_service.get(
                    service.id, Z1
                ),
            }
            row["not_archived"] = (service.effort_rate or Z2) * row[
                "not_archived_logged_hours"
            ] + row["not_archived_logged_cost"]

            logged_hours[service.offer] += row["logged_hours"]
            logged_cost[service.offer] += row["logged_cost"]
            logged_hours[service.project] += row["logged_hours"]
            logged_cost[service.project] += row["logged_cost"]
            total_logged_cost += row["logged_cost"]
            logged_hours_per_effort_rate[service.effort_rate] += row["logged_hours"]

            if not service.is_declined:
                service_hours[service.offer] += service.service_hours
                service_cost[service.offer] += service.cost or Z2
                service_hours[service.project] += service.service_hours
                service_cost[service.project] += service.cost or Z2
                total_service_cost += service.service_cost

            if service.effort_rate is not None:
                total_logged_cost += service.effort_rate * row["logged_hours"]
            else:
                total_logged_hours_rate_undefined += row["logged_hours"]
                if not service.is_declined:
                    total_service_hours_rate_undefined += service.service_hours

            services_by_offer[offers_map.get(service.offer_id)]["services"].append(row)

        for offer, offer_data in services_by_offer.items():
            offer_data["service_hours"] = service_hours[offer]
            offer_data["logged_hours"] = logged_hours[offer]
            offer_data["service_cost"] = service_cost[offer]
            offer_data["logged_cost"] = logged_cost[offer]

        return {
            "offers": sorted(
                item
                for item in services_by_offer.items()
                if item[1]["services"] or item[0] is not None
            ),
            "logged_hours": logged_hours[self],
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
            "logged_cost": logged_cost[self],
            "service_hours": service_hours[self],
            "service_cost": service_cost[self],
            "total_service_cost": total_service_cost,
            "total_logged_cost": total_logged_cost,
            "total_service_hours_rate_undefined": total_service_hours_rate_undefined,
            "total_logged_hours_rate_undefined": total_logged_hours_rate_undefined,
            "total_discount": sum(
                (offer.discount for offer in offers if not offer.is_declined), Z2
            ),
        }

    @cached_property
    def project_invoices(self):
        return self.invoices.select_related("contact__organization").reverse()

    @cached_property
    def project_invoices_total_excl_tax(self):
        return sum(
            (
                invoice.total_excl_tax
                for invoice in self.project_invoices
                if invoice.is_invoiced
            ),
            Z2,
        )

    @cached_property
    def not_archived_total(self):
        # Avoid circular imports
        from workbench.logbook.models import LoggedCost, LoggedHours

        total = Z2
        hours_rate_undefined = Z1

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

        total += (
            LoggedCost.objects.order_by()
            .filter(service__project=self, archived_at__isnull=True)
            .aggregate(Sum("cost"))["cost__sum"]
            or Z2
        )
        return {"total": total, "hours_rate_undefined": hours_rate_undefined}

    def solely_declined_offers_warning(self, *, request):
        from workbench.offers.models import Offer

        if self.closed_on:
            return

        status = set(self.offers.order_by().values_list("status", flat=True))
        if status == {Offer.DECLINED}:
            messages.warning(
                request,
                _(
                    "All offers of project %(project)s are declined."
                    " You might want to close the project now?"
                )
                % {"project": self},
            )

    @property
    def is_logbook_locked(self):
        return self.closed_on and self.closed_on < in_days(-14)


class ServiceQuerySet(SearchQuerySet):
    def choices(self):
        offers = defaultdict(list)
        for service in self.select_related("offer__project", "offer__owned_by"):
            offers[service.offer].append((service.id, str(service)))
        return [("", "----------")] + [
            (offer or _("Not offered yet"), services)
            for offer, services in sorted(
                offers.items(),
                key=lambda item: (
                    item[0] and item[0].offered_on or dt.date.max,
                    item[0] and item[0].pk or 1e100,
                ),
            )
        ]

    def budgeted(self):
        from workbench.offers.models import Offer

        return self.filter(Q(offer__isnull=True) | ~Q(offer__status=Offer.DECLINED))

    def logging(self):
        return self.budgeted().filter(allow_logging=True)

    def editable(self):
        from workbench.offers.models import Offer

        return self.filter(
            Q(offer__isnull=True) | Q(offer__status=Offer.IN_PREPARATION)
        )


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
        on_delete=models.PROTECT,
        related_name="services",
        verbose_name=_("role"),
        blank=True,
        null=True,
    )

    objects = ServiceQuerySet.as_manager()

    def get_absolute_url(self):
        return "%s#service%s" % (self.project.get_absolute_url(), self.pk)

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
    def is_declined(self):
        return self.offer.is_declined if self.offer else False
