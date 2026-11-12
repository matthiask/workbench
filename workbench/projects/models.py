import datetime as dt
from collections import defaultdict
from decimal import Decimal
from functools import total_ordering

from admin_ordering.models import OrderableModel
from django.contrib import messages
from django.core.cache import cache
from django.db import models
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.services.models import ServiceBase
from workbench.tools.formats import Z1, Z2, currency, local_date_format
from workbench.tools.models import Model, MoneyField, SearchQuerySet
from workbench.tools.urls import model_urls
from workbench.tools.validation import in_days, raise_if_errors


class InternalType(OrderableModel):
    name = models.CharField(_("name"), max_length=100)
    description = models.CharField(_("description"), max_length=100, blank=True)
    percentage = models.DecimalField(_("percentage"), max_digits=5, decimal_places=2)
    is_outreach = models.BooleanField(
        _("is outreach"),
        default=False,
        help_text=_(
            "Hours on outreach are compared with accepted deals in the squeeze report."
        ),
    )

    class Meta(OrderableModel.Meta):
        verbose_name = _("internal type")
        verbose_name_plural = _("internal types")

    def __str__(self):
        return f"{self.name} ({self.description}, {self.percentage:.1f}%)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(OUTREACH_IDS_CACHE_KEY)

    save.alters_data = True

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        cache.delete(OUTREACH_IDS_CACHE_KEY)
        return result

    delete.alters_data = True

    @classmethod
    def outreach_ids(cls):
        """IDs of the outreach types; project badges need them in lists, where
        loading the internal type of every project would be one query each.
        Cached per process, other processes see changes within a minute."""
        return cache.get_or_set(
            OUTREACH_IDS_CACHE_KEY,
            lambda: set(
                cls.objects.filter(is_outreach=True).values_list("id", flat=True)
            ),
            timeout=60,
        )


OUTREACH_IDS_CACHE_KEY = "projects-outreach-internal-type-ids"


class InternalTypeUser(models.Model):
    internal_type = models.ForeignKey(
        InternalType, on_delete=models.CASCADE, verbose_name=_("internal type")
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))
    _percentage = models.DecimalField(
        _("percentage"),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Inherit the default internal type percentage if left empty."),
    )

    class Meta:
        verbose_name = _("internal type user")
        verbose_name_plural = _("internal type users")

    def __str__(self):
        return ""

    @property
    def percentage(self):
        return (
            self.internal_type.percentage
            if self._percentage is None
            else self._percentage
        )


class CampaignQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(
            Q(
                id__in=Project.objects
                .open()
                .filter(campaign__isnull=False)
                .values("campaign")
            )
        )

    def closed(self):
        return self.filter(
            ~Q(
                id__in=Project.objects
                .open()
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
        User, on_delete=models.PROTECT, verbose_name=_("contact person")
    )
    _fts = models.TextField(editable=False, blank=True)

    objects = CampaignQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]
        verbose_name = _("campaign")
        verbose_name_plural = _("campaigns")

    def __str__(self):
        return f"{self.code} {self.title} - {self.owned_by.get_short_name()}"

    def __html__(self):
        return format_html(
            "<small>{}</small> {} - {}",
            self.code,
            self.title,
            self.owned_by.get_short_name(),
        )

    def fts_text(self):
        return " ".join(str(part) for part in [self.code, self.customer.name])

    def save(self, *args, **kwargs):
        self._fts = self.fts_text()
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
        from workbench.reporting.squeeze import gross_margin_components

        pbs = project_budget_statistics(self.projects.all())
        overall = pbs["overall"]
        gross_margin = sum(
            (
                row["invoiced"]
                for row in gross_margin_components(self.projects.all()).values()
            ),
            Z2,
        )
        overall["gross_margin_per_hour"] = (
            gross_margin / overall["hours"] if overall["hours"] else None
        )
        pbs["statistics"] = sorted(pbs["statistics"], key=lambda s: s["project"])
        return pbs

    @cached_property
    def logged_hours_per_effort(self):
        """(effort type, hourly rate, hours), highest rates first"""
        from workbench.logbook.models import LoggedHours

        return (
            LoggedHours.objects
            .filter(service__project__campaign=self)
            .values("service__effort_type", "service__effort_rate")
            .annotate(Sum("hours"))
            .values_list("service__effort_type", "service__effort_rate", "hours__sum")
            .order_by("-service__effort_rate", "service__effort_type")
        )


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

    def external(self):
        return self.exclude(type=Project.INTERNAL)

    def closed(self):
        return self.filter(closed_on__isnull=False)

    def orders(self):
        return self.filter(type=Project.ORDER)

    def without_invoices(self):
        from workbench.invoices.models import Invoice

        return self.exclude(
            id__in=Invoice.objects
            .invoiced()
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
                    status__in=(
                        Offer.IN_PREPARATION,
                        Offer.SERVICE_GROUP,
                        Offer.OFFERED,
                        Offer.ACCEPTED,
                    )
                ).values("project")
            )
        )

    def old_projects(self):
        from workbench.logbook.models import LoggedHours

        return (
            self
            .open()
            .filter(
                id__in=LoggedHours.objects
                .filter(archived_at__isnull=True)
                .order_by()
                .values("service__project")
            )
            .exclude(
                id__in=LoggedHours.objects
                .order_by()
                .filter(rendered_on__gte=in_days(-60))
                .values("service__project")
            )
        )

    def own_or_inactive(self, user):
        return self.filter(Q(owned_by=user) | Q(owned_by__is_active=False))

    def invalid_customer_contact_combination(self):
        return self.exclude(customer=F("contact__organization"))

    def no_projected_gross_margin(self):
        from workbench.invoices.models import ProjectedInvoice

        return self.filter(
            ~Q(pk__in=ProjectedInvoice.objects.values_list("project")),
            ~Q(type=Project.INTERNAL),
            Q(closed_on__isnull=True),
        )

    def empty_logbook(self):
        from workbench.logbook.models import LoggedCost, LoggedHours

        return self.open().exclude(
            Q(
                id__in=LoggedHours.objects.filter(
                    service__project__closed_on__isnull=True
                ).values("service__project")
            )
            | Q(
                id__in=LoggedCost.objects.filter(
                    service__project__closed_on__isnull=True
                ).values("service__project")
            )
        )


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
        User, on_delete=models.PROTECT, verbose_name=_("contact person")
    )

    type = models.CharField(
        _("type"), choices=TYPE_CHOICES, max_length=20, default=ORDER
    )
    internal_type = models.ForeignKey(
        InternalType,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="+",
        verbose_name=_("internal type"),
    )
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
    suppress_planning_update_mails = models.BooleanField(
        _("suppress planning update mails for this project for everyone"),
        default=False,
    )
    budget_alert_at = MoneyField(
        _("send a mail when the logged cost reaches"),
        blank=True,
        null=True,
        help_text=_(
            "The contact person receives a mail once. Useful when you agreed"
            " with the customer to get in touch before the cost cap is used up."
        ),
    )
    budget_alert_sent_at = models.DateTimeField(
        _("budget alert sent at"), blank=True, null=True, editable=False
    )

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("project")
        verbose_name_plural = _("projects")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_budget_alert_at = self.budget_alert_at

    def __str__(self):
        return f"{self.code} {self.title} - {self.owned_by.get_short_name()}"

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

    def fts_text(self):
        return " ".join(
            str(part)
            for part in [
                self.code,
                self.customer.name,
                self.contact.full_name if self.contact else "",
            ]
        )

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

        self._fts = self.fts_text()
        if self.budget_alert_at != self._orig_budget_alert_at:
            # A new threshold deserves a new alert.
            self.budget_alert_sent_at = None

        if new:
            super().save()
        else:
            super().save(*args, **kwargs)

        self._orig_budget_alert_at = self.budget_alert_at

    save.alters_data = True

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}
        if self.closed_on and self.closed_on > dt.date.today():
            errors["closed_on"] = _(
                "Leave this empty if you do not want to close the project yet."
            )
        raise_if_errors(errors, exclude)

    @property
    def is_outreach(self):
        return (
            self.type == self.INTERNAL
            and self.internal_type_id in InternalType.outreach_ids()
        )

    @property
    def status_badge(self):
        # Colors in main.scss ($project-type-colors), closed projects outlined
        kind = "outreach" if self.is_outreach else self.type
        css = f"wb-project-type wb-project-type--{kind}"
        if self.closed_on:
            css += " wb-project-type--closed"
        return format_html('<span class="badge {}">{}</span>', css, self.pretty_status)

    @property
    def pretty_status(self):
        parts = [str(self.get_type_display())]
        if self.is_outreach:
            parts = [f"{parts[0]} · {gettext('Outreach')}"]
        if self.closed_on:
            parts.append(gettext("closed on %s") % local_date_format(self.closed_on))
        return ", ".join(parts)

    @cached_property
    def grouped_services(self):
        # Avoid circular imports
        from workbench.deals.models import Deal
        from workbench.logbook.models import (
            HOURS_FOR_INVOICING,
            LoggedCost,
            LoggedHours,
        )
        from workbench.reporting.utils import sum_by

        # Logged vs. service hours
        service_hours = defaultdict(lambda: Z1)
        logged_hours = defaultdict(lambda: Z1)
        # Hours for invoicing above the hours use up the budget too
        surcharge = defaultdict(lambda: Z1)
        # Logged vs. service cost
        service_cost = defaultdict(lambda: Z2)
        logged_cost = defaultdict(lambda: Z2)
        # Hours for invoicing and costs not invoiced yet, keyed (field, offer or project)
        not_archived = defaultdict(lambda: Z2)
        # Project logbook vs. project service cost (hours and cost)
        total_service_cost = Z2
        released_service_cost = Z2
        total_service_third_party_costs = Z2
        accepted_offers_service_cost = Z2
        total_logged_cost = Z2
        total_service_hours_rate_undefined = Z1
        total_logged_hours_rate_undefined = Z1

        offers = self.offers.select_related("owned_by").prefetch_related(
            Prefetch("deals", Deal.objects.select_related("owned_by")), "headings"
        )
        offers_map = {offer.id: offer for offer in offers}
        services_by_offer = defaultdict(
            lambda: {"services": []}, ((offer, {"services": []}) for offer in offers)
        )

        logged_hours_per_service_and_user = defaultdict(dict)
        hours_for_invoicing_per_service = defaultdict(lambda: Z1)
        surcharge_per_service = defaultdict(lambda: Z1)
        logged_hours_per_user = defaultdict(lambda: Z1)
        logged_hours_per_effort = defaultdict(lambda: Z1)
        # Entries with invoiced hours, for sanity checks
        hours_for_invoicing_entries = 0
        hours_for_invoicing_more = hours_for_invoicing_less = Z1
        difference = F("hours_for_invoicing") - F("hours")

        for row in (
            LoggedHours.objects
            .order_by()
            .filter(service__project=self)
            .values("service", "rendered_by")
            .annotate(
                Sum("hours"),
                hours_for_invoicing_sum=Sum(HOURS_FOR_INVOICING),
                hours_for_invoicing_entries=Count(
                    "id", filter=Q(hours_for_invoicing__isnull=False)
                ),
                # Separately, entries worth less don't cancel out others
                hours_for_invoicing_more=Sum(
                    difference, filter=Q(hours_for_invoicing__gt=F("hours"))
                ),
                hours_for_invoicing_less=Sum(
                    difference, filter=Q(hours_for_invoicing__lt=F("hours"))
                ),
            )
        ):
            logged_hours_per_user[row["rendered_by"]] += row["hours__sum"]
            hours_for_invoicing_entries += row["hours_for_invoicing_entries"]
            hours_for_invoicing_more += row["hours_for_invoicing_more"] or Z1
            surcharge_per_service[row["service"]] += (
                row["hours_for_invoicing_more"] or Z1
            )
            hours_for_invoicing_less += row["hours_for_invoicing_less"] or Z1
            hours_for_invoicing_per_service[row["service"]] += row[
                "hours_for_invoicing_sum"
            ]
            logged_hours_per_service_and_user[row["service"]][row["rendered_by"]] = row[
                "hours__sum"
            ]

        logged_cost_per_service = sum_by(
            LoggedCost.objects.filter(service__project=self),
            key="service",
            field="cost",
        )
        not_archived_logged_hours_per_service = sum_by(
            LoggedHours.objects.filter(
                service__project=self,
                archived_at__isnull=True,
            ),
            key="service",
            field=HOURS_FOR_INVOICING,
            default=Z1,
        )
        not_archived_logged_cost_per_service = sum_by(
            LoggedCost.objects.filter(service__project=self, archived_at__isnull=True),
            key="service",
            field="cost",
        )

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
                "surcharge": surcharge_per_service[service.id],
                "logged_cost": logged_cost_per_service[service.id],
                "not_archived_logged_hours": not_archived_logged_hours_per_service[
                    service.id
                ],
                "not_archived_logged_cost": not_archived_logged_cost_per_service[
                    service.id
                ],
            }
            row["not_archived"] = (service.effort_rate or Z2) * row[
                "not_archived_logged_hours"
            ] + row["not_archived_logged_cost"]

            logged_hours[service.offer] += row["logged_hours"]
            logged_cost[service.offer] += row["logged_cost"]
            for key in ["not_archived_logged_hours", "not_archived_logged_cost"]:
                not_archived[key, service.offer] += row[key]
                not_archived[key, service.project] += row[key]
            logged_hours[service.project] += row["logged_hours"]
            surcharge[service.offer] += row["surcharge"]
            surcharge[service.project] += row["surcharge"]
            logged_cost[service.project] += row["logged_cost"]
            total_logged_cost += row["logged_cost"]
            logged_hours_per_effort[service.effort_type, service.effort_rate] += row[
                "logged_hours"
            ]

            if (
                not service.is_declined
                and not service.is_optional
                and not service.is_budget_retainer
            ):
                service_hours[service.offer] += service.service_hours
                service_cost[service.offer] += service.cost or Z2
                service_hours[service.project] += service.service_hours
                service_cost[service.project] += service.cost or Z2
                total_service_cost += service.service_cost
                if service.offer is None:
                    released_service_cost += service.service_cost
                total_service_third_party_costs += service.third_party_costs or Z2
                if service.offer and service.offer.is_accepted:
                    accepted_offers_service_cost += service.service_cost

            if service.effort_rate is not None:
                total_logged_cost += (
                    service.effort_rate * hours_for_invoicing_per_service[service.id]
                )
            else:
                total_logged_hours_rate_undefined += row["logged_hours"]
                if (
                    not service.is_declined
                    and not service.is_optional
                    and not service.is_budget_retainer
                ):
                    total_service_hours_rate_undefined += service.service_hours

            services_by_offer[offers_map.get(service.offer_id)]["services"].append(row)

        for offer, offer_data in services_by_offer.items():
            # Services and the offer's headings in the order they're shown
            offer_data["items"] = sorted(
                [
                    *offer_data["services"],
                    *(
                        {"heading": heading}
                        for heading in (offer.headings.all() if offer else ())
                    ),
                ],
                key=lambda item: (
                    (item.get("heading") or item.get("service")).position,
                    "heading" not in item,
                ),
            )
            offer_data["service_hours"] = service_hours[offer]
            offer_data["logged_hours"] = logged_hours[offer]
            offer_data["surcharge"] = surcharge[offer]
            offer_data["service_cost"] = service_cost[offer]
            offer_data["logged_cost"] = logged_cost[offer]
            offer_data["not_archived_logged_hours"] = not_archived[
                "not_archived_logged_hours", offer
            ]
            offer_data["not_archived_logged_cost"] = not_archived[
                "not_archived_logged_cost", offer
            ]

        stats = {
            "offers": sorted(
                item
                for item in services_by_offer.items()
                if item[1]["services"] or item[0] is not None
            ),
            "logged_hours": logged_hours[self],
            "surcharge": surcharge[self],
            "hours_for_invoicing_entries": hours_for_invoicing_entries,
            "hours_for_invoicing_more": hours_for_invoicing_more,
            "hours_for_invoicing_less": hours_for_invoicing_less,
            "logged_hours_per_user": sorted(
                ((users[user], hours) for user, hours in logged_hours_per_user.items()),
                key=lambda row: row[1],
                reverse=True,
            ),
            # (effort type, hourly rate, hours): undefined rates first (they
            # are warnings), then the highest rates
            "logged_hours_per_effort": sorted(
                (
                    (effort_type, rate, hours)
                    for (effort_type, rate), hours in logged_hours_per_effort.items()
                    if hours
                ),
                key=lambda row: (row[1] is not None, -(row[1] or 0), row[0]),
            ),
            "logged_cost": logged_cost[self],
            "not_archived_logged_hours": not_archived[
                "not_archived_logged_hours", self
            ],
            "not_archived_logged_cost": not_archived["not_archived_logged_cost", self],
            "service_hours": service_hours[self],
            "service_cost": service_cost[self],
            "total_service_cost": total_service_cost,
            "total_service_third_party_costs": total_service_third_party_costs,
            "accepted_offers_service_cost": accepted_offers_service_cost,
            "not_accepted_service_cost": total_service_cost
            - accepted_offers_service_cost,
            "total_logged_cost": total_logged_cost,
            "total_service_hours_rate_undefined": total_service_hours_rate_undefined,
            "total_logged_hours_rate_undefined": total_logged_hours_rate_undefined,
            "total_discount": sum(
                (offer.discount for offer in offers if not offer.is_declined), Z2
            ),
            "accepted_offers_discount": sum(
                (offer.discount for offer in offers if offer.is_accepted), Z2
            ),
            "accepted_offers_total_excl_tax": sum(
                (offer.total_excl_tax for offer in offers if offer.is_accepted), Z2
            ),
            # Budget retainment
            "has_budget_retainer_offers": any(
                offer.is_budget_retainer for offer in offers
            ),
            "budget_retainer_total": sum(
                (
                    offer.total_excl_tax
                    for offer in offers
                    if offer.is_budget_retainer and offer.is_accepted
                ),
                Z2,
            ),
            "budget_retainer_discount": sum(
                (
                    offer.discount
                    for offer in offers
                    if offer.is_budget_retainer and offer.is_accepted
                ),
                Z2,
            ),
            "warnings": [],
        }

        # Budget retainers are released with services without offer
        stats["released_service_cost"] = released_service_cost
        stats["budget_retainment"] = (
            stats["budget_retainer_total"] - released_service_cost
        )

        if stats["budget_retainment"] > 0 and stats["total_logged_cost"] > stats[
            "total_service_cost"
        ] * Decimal("1.1"):
            stats["warnings"].append(
                _(
                    "This project uses budget retaining offers. The logged cost is significantly larger than the allocated cost."
                )
            )

        return stats

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
        from workbench.reporting.utils import effort_cost_by_project, sum_of

        effort = effort_cost_by_project(
            LoggedHours.objects.filter(service__project=self, archived_at__isnull=True)
        )[self.id]
        costs = sum_of(
            LoggedCost.objects.filter(service__project=self, archived_at__isnull=True),
            field="cost",
        )
        return {
            "total": effort["cost"] + costs,
            "hours_rate_undefined": effort["hours_rate_undefined"],
        }

    def solely_declined_offers_warning(self, *, request):
        from workbench.offers.models import Offer

        if self.closed_on:
            return

        status = set(self.offers.order_by().values_list("status", flat=True))
        if status and status <= set(Offer.NOT_PURSUED):
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

    def create_invoice_warnings(self, invoice_type):
        invoice_class = self.invoices.model
        warnings = []
        if self.invoices.filter(status=invoice_class.IN_PREPARATION).exists():
            warnings.append((
                "already-one-in-preparation",
                _("This project already has an invoice in preparation."),
            ))

        types = list(self.invoices.invoiced().order_by().values_list("type", flat=True))
        if invoice_type == invoice_class.FIXED and invoice_class.SERVICES in types:
            warnings.append((
                "type-change",
                _(
                    "This project already used service invoices but you are now creating a fixed amount invoice. Take care to not send invoices for the same services twice!"
                ),
            ))
        if invoice_type == invoice_class.SERVICES and invoice_class.FIXED in types:
            warnings.append((
                "type-change",
                _(
                    "This project already used fixed amount invoices but you are now creating a services invoice. Take care to not send invoices for the same services twice!"
                ),
            ))
        return warnings


class ServiceQuerySet(SearchQuerySet):
    def invoiced(self):
        """Services invoiced from the logbook or from the offer, cancelled
        invoices don't count"""
        from workbench.invoices.models import Invoice, Service as InvoiceService

        return self.filter(
            Exists(
                InvoiceService.objects.filter(project_service=OuterRef("pk")).exclude(
                    invoice__status=Invoice.CANCELED
                )
            )
        )

    def choices_with_pins(self, *, project, user):
        choices = self.choices()
        if pinned := self.filter(id__in=user.pinned_services.filter(project=project)):
            choices.insert(
                1,
                (
                    _("Pinned"),
                    [(service.id, str(service)) for service in pinned],
                ),
            )
        return choices

    def choices(self):
        offers = defaultdict(list)
        for service in self.select_related("offer__project", "offer__owned_by"):
            offers[service.offer].append((service.id, str(service)))
        return [("", "----------")] + [
            (offer or _("Not offered yet"), services)
            for offer, services in sorted(offers.items())
        ]

    def budgeted(self):
        from workbench.offers.models import Offer

        return self.filter(
            (
                Q(offer__isnull=True)
                | ~(
                    Q(offer__status__in=Offer.NOT_PURSUED)
                    | Q(offer__is_budget_retainer=True)
                )
            )
            & Q(is_optional=False)
        )

    def logging(self):
        from workbench.offers.models import Offer

        return self.filter(
            Q(allow_logging=True),
            Q(offer__isnull=True)
            | ~(
                Q(offer__status__in=Offer.NOT_PURSUED)
                | Q(offer__work_completed_on__isnull=False)
                | Q(offer__is_budget_retainer=True)
            ),
        )

    def editable(self):
        from workbench.offers.models import Offer

        return self.filter(
            Q(offer__isnull=True)
            | Q(offer__status__in=[Offer.IN_PREPARATION, Offer.SERVICE_GROUP])
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
    external_reference = models.URLField(
        _("external reference"),
        max_length=500,
        blank=True,
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
        help_text=_("Optional services do not count towards the offer total."),
    )

    objects = ServiceQuerySet.as_manager()

    def get_absolute_url(self):
        return f"{self.project.get_absolute_url()}#service{self.pk}"

    @classmethod
    def allow_update(cls, instance, request):
        return True

    @classmethod
    def allow_delete(cls, instance, request):
        # Service groups haven't been sent
        if instance.offer and not instance.offer.services_changeable:
            messages.error(
                request,
                _(
                    "Cannot delete a service bound to an offer"
                    " which is not in preparation anymore."
                ),
            )
            return False
        if instance.is_invoiced:
            messages.error(
                request,
                _("This service has been invoiced already, it cannot be deleted."),
            )
            return False
        return super().allow_delete(instance, request)

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return instance.get_absolute_url() if instance else "projects_project_list"
        return None

    @property
    def is_invoiced(self):
        """Invoiced from the logbook or from the offer: the invoice's lines
        point to the service, so it stays where it is (unless the invoices
        have been cancelled)"""
        return (
            self.pk is not None
            and type(self).objects.filter(pk=self.pk).invoiced().exists()
        )

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}
        if self.offer and self.offer.project_id != self.project_id:
            errors["offer"] = _(
                "The offer must belong to the same project as the service."
            )
        raise_if_errors(errors, exclude)

    @property
    def is_declined(self):
        return self.offer.is_declined if self.offer else False

    @property
    def is_work_completed(self):
        return bool(self.offer.work_completed_on) if self.offer else False

    @property
    def is_budget_retainer(self):
        return self.offer.is_budget_retainer if self.offer else False

    def is_logging_allowed(self):
        return (
            self.allow_logging
            and not self.is_declined
            and not self.is_work_completed
            and not self.is_budget_retainer
        )


class BudgetTransferQuerySet(models.QuerySet):
    def reserved(self):
        return self.filter(to_project__isnull=True)

    def adjustments(self, *, projects=None):
        """
        Net budget adjustment per project as ``{project_id: amount}``.

        Only money moves. The hours are already in the right place: they were
        logged on whichever project the work actually happened on.

        Budget leaves the project it was reserved on immediately -- whether or
        not a target project exists yet -- and arrives on the target project as
        soon as one is named.
        """
        adjustments = defaultdict(lambda: Z2)
        queryset = self
        if projects is not None:
            queryset = queryset.filter(
                Q(from_project__in=projects) | Q(to_project__in=projects)
            )
        for from_project, to_project, amount in queryset.values_list(
            "from_project", "to_project", "amount"
        ):
            adjustments[from_project] -= amount
            if to_project:
                adjustments[to_project] += amount
        return adjustments


@model_urls
class BudgetTransfer(Model):
    """
    Budget which has been invoiced on one project but is worked off on another,
    for example a share of a campaign website's budget reserved for a later
    re-conception.

    Closed projects cannot be reopened, so without this the hours end up on a
    project which never saw any revenue: the people on the original project get
    credited with an implausibly high hourly rate, the people on the later one
    with none at all. Moving the budget puts the money next to the hours it
    actually paid for.

    ``to_project`` may be empty. The budget then counts as reserved: it has
    already left the source project -- which is what keeps that project's rate
    honest -- but has not arrived anywhere yet. Splitting a reserved amount
    across several projects means narrowing this transfer and adding another.
    """

    open_in_modal = True

    from_project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("from project"),
        related_name="budget_transfers_out",
    )
    to_project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("to project"),
        related_name="budget_transfers_in",
        help_text=_(
            "Leave this empty to only reserve the budget for now. It stops"
            " counting towards the source project either way."
        ),
    )
    title = models.CharField(_("title"), max_length=200)
    amount = MoneyField(_("amount"))
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("created by"),
        related_name="+",
    )

    objects = BudgetTransferQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("budget transfer")
        verbose_name_plural = _("budget transfers")

    def __str__(self):
        return f"{self.title} ({currency(self.amount)})"

    def get_absolute_url(self):
        return f"{self.from_project.get_absolute_url()}#budgettransfer{self.pk}"

    @property
    def is_reserved(self):
        return self.to_project_id is None

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}

        if self.to_project_id and self.to_project_id == self.from_project_id:
            errors["to_project"] = _(
                "Moving budget to the same project does not do anything."
            )

        raise_if_errors(errors, exclude)
