import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.db import models
from django.db.models import F, Q, Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.services.models import ServiceBase
from workbench.tools.formats import local_date_format
from workbench.tools.models import Model, MoneyField, SearchQuerySet, Z
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


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
            id__in=Invoice.objects.valid()
            .filter(project__isnull=False)
            .values("project")
        )

    def with_accepted_offers(self):
        from workbench.offers.models import Offer

        return self.filter(id__in=Offer.objects.accepted().values("project"))

    def old_projects(self):
        from workbench.logbook.models import LoggedHours

        return (
            self.open()
            .filter(id__in=LoggedHours.objects.order_by().values("service__project"))
            .exclude(
                id__in=LoggedHours.objects.order_by()
                .filter(rendered_on__gte=dt.date.today() - dt.timedelta(days=60))
                .values("service__project")
            )
        )

    def invalid_customer_contact_combination(self):
        return self.open().exclude(customer=F("contact__organization"))


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
    description = models.TextField(_("description"), blank=True)
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

        offers = self.offers.select_related("owned_by")
        offers_map = {offer.id: offer for offer in offers}
        services_by_offer = defaultdict(list, {offer: [] for offer in offers})

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

            services_by_offer[offers_map.get(service.offer_id)].append(row)

        return {
            "offers": sorted(
                (
                    item
                    for item in services_by_offer.items()
                    if item[1] or item[0] is not None
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
        from workbench.logbook.models import LoggedCost, LoggedHours

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

        total += (
            LoggedCost.objects.order_by()
            .filter(service__project=self, archived_at__isnull=True)
            .aggregate(Sum("cost"))["cost__sum"]
            or Z
        )
        return {"total": total, "hours_rate_undefined": hours_rate_undefined}


class ServiceQuerySet(models.QuerySet):
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

        return self.filter(Q(offer__isnull=True) | ~Q(offer__status=Offer.REJECTED))

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
        on_delete=models.SET_NULL,
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
    def is_rejected(self):
        return self.offer.is_rejected if self.offer else False
