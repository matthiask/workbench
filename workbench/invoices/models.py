import datetime as dt

from django.conf import settings
from django.contrib import messages
from django.db import connections, models
from django.db.models import Case, F, Q, Sum, When
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import format_html
from django.utils.timesince import timesince
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction
from workbench.contacts.models import Organization, Person
from workbench.invoices.utils import recurring
from workbench.logbook.models import HOURS_FOR_INVOICING, LoggedCost, LoggedHours
from workbench.projects.models import Project
from workbench.reporting.models import FreezeDate
from workbench.services.models import ServiceBase
from workbench.tools.formats import Z1, Z2, currency, local_date_format
from workbench.tools.models import (
    ModelWithTotal,
    MoneyField,
    SearchQuerySet,
    default_tax_rate,
)
from workbench.tools.urls import model_urls
from workbench.tools.validation import in_days, raise_if_errors


class InvoiceQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(status__in=(Invoice.IN_PREPARATION, Invoice.SENT))

    def invoiced(self):
        return self.filter(status__in=Invoice.INVOICED_STATUSES)

    def outstanding(self, *, on):
        """Invoices which have been sent but not paid yet on the given date"""
        return self.invoiced().filter(
            Q(invoiced_on__lte=on), Q(closed_on__gt=on) | Q(closed_on__isnull=True)
        )

    def due(self):
        return self.filter(
            status=Invoice.SENT, due_on__isnull=False, due_on__lte=dt.date.today()
        )

    def overdue(self):
        return self.filter(
            Q(postpone_reminders_until__isnull=True)
            | Q(postpone_reminders_until__lte=dt.date.today()),
            status=Invoice.SENT,
            due_on__isnull=False,
            due_on__lte=in_days(-15),
        ).exclude(type=Invoice.CREDIT)

    def autodunning(self):
        return self.overdue().filter(
            Q(last_reminded_on__isnull=True) | Q(last_reminded_on__lte=in_days(-30))
        )

    def maybe_actionable(self, *, user):
        return (
            self
            .filter(
                Q(status=Invoice.IN_PREPARATION)
                | (
                    Q(
                        status=Invoice.SENT,
                        due_on__isnull=False,
                        due_on__lte=in_days(-15),
                    )
                    & ~Q(type=Invoice.CREDIT)
                ),
                Q(owned_by=user)
                | Q(owned_by__is_active=False, project__isnull=True)
                | Q(owned_by__is_active=False, project__owned_by__is_active=False)
                | Q(owned_by__is_active=False, project__owned_by=user),
            )
            .select_related("project", "owned_by")
            .order_by(
                # Overdue invoices first, longest overdue first, then those in
                # preparation (which have a due date too), oldest first
                Case(When(status=Invoice.SENT, then=0), default=1),
                F("due_on").asc(nulls_last=True),
                "created_at",
                "pk",
            )
        )


@model_urls
class Invoice(ModelWithTotal):
    # Reminders may be postponed at most this far into the future. Anything
    # beyond this isn't a clarification anymore, it's forgetting about the
    # invoice.
    MAX_POSTPONE_REMINDERS_DAYS = 60
    # Postponements longer than this are possible but have to be confirmed.
    UNEXPECTED_POSTPONE_REMINDERS_DAYS = 30

    IN_PREPARATION = 10
    SENT = 20
    PAID = 40
    CANCELED = 50

    STATUS_CHOICES = (
        (IN_PREPARATION, _("In preparation")),
        (SENT, _("Sent")),
        (PAID, _("Paid")),
        (CANCELED, _("Canceled")),
    )
    INVOICED_STATUSES = {SENT, PAID}

    FIXED = "fixed"
    DOWN_PAYMENT = "down-payment"
    SERVICES = "services"
    CREDIT = "credit"

    TYPE_CHOICES = (
        (FIXED, _("Fixed amount")),
        (DOWN_PAYMENT, _("Down payment")),
        (SERVICES, _("Services")),
        (CREDIT, _("Credit")),
    )

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
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("project"),
        related_name="invoices",
    )

    invoiced_on = models.DateField(_("invoiced on"), blank=True, null=True)
    due_on = models.DateField(_("due on"), blank=True, null=True)
    closed_on = models.DateField(
        _("closed on"),
        blank=True,
        null=True,
        help_text=_(
            "Payment date for paid invoices, date of"
            " replacement or cancellation otherwise."
        ),
    )
    last_reminded_on = models.DateField(_("last reminded on"), blank=True, null=True)
    postpone_reminders_until = models.DateField(
        _("postpone reminders until"),
        blank=True,
        null=True,
        help_text=_(
            "The invoice is left out of the reminders list until this date,"
            " for example while a question of the customer is being clarified."
        ),
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    service_period_from = models.DateField(
        _("service period from"), blank=True, null=True
    )
    service_period_until = models.DateField(
        _("service period until"), blank=True, null=True
    )
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("contact person")
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=IN_PREPARATION
    )
    type = models.CharField(_("type"), max_length=20, choices=TYPE_CHOICES)
    down_payment_applied_to = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("down payment applied to"),
        related_name="down_payment_invoices",
    )
    down_payment_total = MoneyField(_("down payment total"), default=Z2)
    third_party_costs = MoneyField(
        _("third party costs"),
        default=Z2,
        help_text=_("Only used for statistical purposes."),
    )

    postal_address = models.TextField(_("postal address"))

    _code = models.IntegerField(_("code"))
    _fts = models.TextField(editable=False, blank=True)

    payment_notice = models.TextField(
        _("payment notice"),
        blank=True,
        help_text=_("Assigning a credit entry adds its details."),
    )

    archived_at = models.DateTimeField(_("freezed at"), blank=True, null=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_status = self.status

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
        return " ".join(
            str(part)
            for part in [
                self.code,
                self.customer.name,
                self.contact.full_name if self.contact else "",
                self.project.title if self.project else "",
            ]
        )

    def save(self, *args, **kwargs):
        new = not self.pk
        if new:
            if self.project_id:
                self._code = RawSQL(
                    "SELECT COALESCE(MAX(_code), 0) + 1 FROM invoices_invoice"
                    " WHERE project_id = %s",
                    (self.project_id,),
                )
            else:
                self._code = RawSQL(
                    "SELECT COALESCE(MAX(_code), 0) + 1 FROM invoices_invoice"
                    " WHERE project_id IS NULL",
                    (),
                )
            super().save(*args, **kwargs)
            self.refresh_from_db()

        self._fts = self.fts_text()
        if (
            self.invoiced_on
            and self.last_reminded_on
            and self.last_reminded_on < self.invoiced_on
        ):
            # Reset last_reminded_on if it is before invoiced_on
            self.last_reminded_on = None

        if new:
            super().save()
        else:
            super().save(*args, **kwargs)

        if self.status == self.CANCELED:
            self._unlink_logbook()
            self._unlink_down_payments()

    save.alters_data = True

    def delete(self, *args, **kwargs):
        assert self.status <= self.IN_PREPARATION, (
            "Trying to delete an invoice not in preparation"
        )
        super().delete(*args, **kwargs)

    delete.alters_data = True

    def _calculate_total(self):
        if self.type == self.SERVICES:
            services = self.services.all() if self.pk else []
            self.subtotal = sum((service.service_cost for service in services), Z2)
            self.third_party_costs = sum(
                (
                    service.third_party_costs
                    for service in services
                    if service.third_party_costs
                ),
                Z2,
            )
        super()._calculate_total()

    @property
    def code(self):
        return (
            "%s-%04d" % (self.project.code, self._code)
            if self.project
            else "%05d" % self._code
        )

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}

        if self.status >= self.SENT and (not self.invoiced_on or not self.due_on):
            errors["status"] = _("Invoice and/or due date missing for selected state.")

        if self.status <= self.SENT and self.closed_on:
            errors["status"] = _("Invalid status when closed on is already set.")

        if self.invoiced_on and self.due_on and self.invoiced_on > self.due_on:
            errors["due_on"] = _("Due date has to be after invoice date.")

        if self.postpone_reminders_until and self.postpone_reminders_until > in_days(
            self.MAX_POSTPONE_REMINDERS_DAYS
        ):
            errors["postpone_reminders_until"] = _(
                "Reminders cannot be postponed by more than %(days)s days"
                " (that would be later than %(date)s)."
            ) % {
                "days": self.MAX_POSTPONE_REMINDERS_DAYS,
                "date": local_date_format(in_days(self.MAX_POSTPONE_REMINDERS_DAYS)),
            }

        if (
            self.type in {self.SERVICES, self.DOWN_PAYMENT, self.CREDIT}
            and not self.project
        ):
            errors["__all__"] = _("Invoices of type %(type)s require a project.") % {
                "type": self.get_type_display()
            }

        if self.status == Invoice.CANCELED and not self.payment_notice:
            errors["payment_notice"] = _(
                "Please provide a short reason for the invoice cancellation."
            )
        if self.status == Invoice.PAID and not self.payment_notice:
            # Assigning credit entries writes their details
            errors["payment_notice"] = _(
                "Please provide a short payment notice, e.g. when and how the"
                " invoice has been paid."
            )

        if bool(self.service_period_from) != bool(self.service_period_until):
            errors["service_period_from"] = errors["service_period_until"] = _(
                "Either fill in both fields or none."
            )
        if (
            self.service_period_from
            and self.service_period_until
            and self.service_period_from > self.service_period_until
        ):
            errors["service_period_until"] = _("Until date has to be after from date.")

        raise_if_errors(errors, exclude)

    @property
    def is_invoiced(self):
        return self.status in self.INVOICED_STATUSES

    @property
    def is_freezed(self):
        if self.archived_at:
            return True

        if (
            self.status >= self.SENT
            and self.invoiced_on
            and (freeze := FreezeDate.objects.up_to())
        ):
            return self.invoiced_on <= freeze

        return False

    @property
    def pretty_status(self):
        d = {
            "invoiced_on": (
                local_date_format(self.invoiced_on) if self.invoiced_on else None
            ),
            "due_on": (local_date_format(self.due_on) if self.due_on else None),
            "reminded_on": (
                local_date_format(self.last_reminded_on)
                if self.last_reminded_on
                else None
            ),
            "created_at": local_date_format(self.created_at.date()),
            "closed_on": (
                local_date_format(self.closed_on) if self.closed_on else None
            ),
            "postponed_until": (
                local_date_format(self.postpone_reminders_until)
                if self.postpone_reminders_until
                else None
            ),
        }

        if self.status == self.IN_PREPARATION:
            return _("In preparation since %(created_at)s") % d
        if self.status == self.SENT:
            if self.reminders_are_postponed:
                return (
                    _(
                        "Sent on %(invoiced_on)s,"
                        " reminders postponed until %(postponed_until)s"
                    )
                    % d
                )

            if self.last_reminded_on:
                return _("Sent on %(invoiced_on)s, reminded on %(reminded_on)s") % d

            if self.due_on:
                return _("Sent on %(invoiced_on)s, due on %(due_on)s") % d

            return _("Sent on %(invoiced_on)s") % d
        if self.status == self.PAID:
            return _("Paid on %(closed_on)s") % d
        return self.get_status_display()

    @property
    def pretty_last_reminded_on(self):
        if self.last_reminded_on:
            if self.last_reminded_on == dt.date.today():
                relative = gettext("today")
            else:
                relative = timesince(self.last_reminded_on, depth=1)
            return f"{local_date_format(self.last_reminded_on)} ({relative})"
        return gettext("Not reminded yet")

    @property
    def reminders_are_postponed(self):
        return bool(
            self.postpone_reminders_until
            and self.postpone_reminders_until > dt.date.today()
        )

    def payment_reminders_sent_at(self):
        from workbench.tools.history import (
            changes,  # Avoid a circular import
        )

        actions = LoggedAction.objects.for_model(self).with_data(id=self.id)
        return [
            day
            for day in [
                change.values["last_reminded_on"]
                for change in changes(self, {"last_reminded_on"}, actions)
            ]
            if day
        ]

    @property
    def status_badge(self):
        css = {
            self.IN_PREPARATION: "info",
            self.SENT: "success",
            self.PAID: "light",
            self.CANCELED: "danger",
        }[self.status]

        if self.status == self.SENT and (
            self.last_reminded_on or (self.due_on and dt.date.today() > self.due_on)
        ):
            css = "warning"

        return format_html(
            '<span class="badge text-bg-{}" data-bs-toggle="tooltip" title="{}">'
            "{}</span>",
            css,
            self.status_details,
            self.pretty_status,
        )

    @property
    def status_details(self):
        """All dates of the invoice and its service period, one per line"""

        def line(text, day):
            return text % {"day": local_date_format(day)} if day else None

        lines = [
            line(_("Created on %(day)s"), self.created_at.date()),
            line(_("Invoiced on %(day)s"), self.invoiced_on),
            line(_("Due on %(day)s"), self.due_on),
            line(_("Last reminded on %(day)s"), self.last_reminded_on),
        ]
        if self.reminders_are_postponed:
            lines.append(
                line(
                    _("Reminders postponed until %(day)s"),
                    self.postpone_reminders_until,
                )
            )
        if self.status == self.PAID:
            lines.append(line(_("Paid on %(day)s"), self.closed_on))
        elif self.status == self.CANCELED:
            lines.append(line(_("Canceled on %(day)s"), self.closed_on))
        if self.service_period:
            lines.append(_("Service period %s") % self.service_period)
        return "\n".join(str(line) for line in lines if line)

    def invoiced_hours(self):
        """The hours of the invoice's services (hours for invoicing)"""
        return self.services.aggregate(hours=Sum("effort_hours", default=Z1))["hours"]

    @property
    def subtotal_title(self):
        if self.type == self.DOWN_PAYMENT:
            return _("Total excl. tax")
        return _("Subtotal")

    @property
    def total_title(self):
        if self.type == self.DOWN_PAYMENT:
            return (
                _("Down payment total %(currency)s incl. tax")
                if self.liable_to_vat
                else _("Down payment total %(currency)s")
            ) % {"currency": settings.WORKBENCH.CURRENCY}
        if self.type == self.CREDIT:
            return (
                _("Credit total %(currency)s incl. tax")
                if self.liable_to_vat
                else _("Credit total %(currency)s")
            ) % {"currency": settings.WORKBENCH.CURRENCY}
        return (
            _("Total %(currency)s incl. tax")
            if self.liable_to_vat
            else _("Total %(currency)s")
        ) % {"currency": settings.WORKBENCH.CURRENCY}

    def _ordered_services(self, project_services):
        return [
            service
            for _offer, service in sorted(
                (service.offer, service) for service in project_services
            )
        ]

    # Where the lines of services invoices come from
    OFFER = "offer"
    LOGBOOK = "logbook"
    # Logged work beyond what has been invoiced already, e.g. after
    # invoicing the offer
    SURPLUS = "surplus"

    def create_services_from_logbook(
        self, project_services, *, logbook_cutoff_date=None
    ):
        self.create_services(
            project_services,
            sources=dict.fromkeys((ps.id for ps in project_services), self.LOGBOOK),
            logbook_cutoff_date=logbook_cutoff_date,
        )

    def create_services_from_offer(self, project_services):
        self.create_services(
            project_services,
            sources=dict.fromkeys((ps.id for ps in project_services), self.OFFER),
        )

    def create_services(self, project_services, *, sources, logbook_cutoff_date=None):
        """Invoice lines for the services as offered, as logged (the entries
        not invoiced yet) or for the surplus, by ``sources`` (service ID to
        source); the logbook cutoff date doesn't apply to offered services"""
        assert self.project, "cannot call create_services without project"

        for position, ps in enumerate(self._ordered_services(project_services)):
            source = sources[ps.id]
            not_archived_effort = ps.loggedhours.filter(
                archived_at__isnull=True
            ).order_by()
            not_archived_costs = ps.loggedcosts.filter(
                archived_at__isnull=True
            ).order_by()
            service = Service(
                invoice=self,
                project_service=ps,
                title=ps.title,
                description=ps.description,
                position=position + 1,
                effort_rate=ps.effort_rate,
                effort_type=ps.effort_type,
            )

            if source == self.OFFER:
                service.effort_hours = ps.effort_hours
                service.cost = ps.cost
                service.third_party_costs = ps.third_party_costs
                service.from_offer = True
            else:
                if logbook_cutoff_date:
                    not_archived_effort = not_archived_effort.filter(
                        rendered_on__lte=logbook_cutoff_date
                    )
                    not_archived_costs = not_archived_costs.filter(
                        rendered_on__lte=logbook_cutoff_date
                    )
                if source == self.SURPLUS:
                    surplus = service_surplus(
                        ps, logbook_cutoff_date=logbook_cutoff_date
                    )
                    service.effort_hours = surplus["hours"]
                    service.cost = surplus["cost"]
                    service.third_party_costs = surplus["third_party_costs"] or None
                else:
                    service.effort_hours = (
                        not_archived_effort.aggregate(s=Sum(HOURS_FOR_INVOICING))["s"]
                        or Z1
                    )
                    service.cost = (
                        not_archived_costs.aggregate(s=Sum("cost"))["s"] or Z2
                    )
                    service.third_party_costs = not_archived_costs.filter(
                        third_party_costs__isnull=False
                    ).aggregate(s=Sum("third_party_costs"))["s"]
                if not (service.effort_hours or service.cost):
                    continue

            service.save(skip_related_model=True)
            not_archived_effort.update(
                invoice_service=service, archived_at=timezone.now()
            )
            not_archived_costs.update(
                invoice_service=service, archived_at=timezone.now()
            )

        (
            self.service_period_from,
            self.service_period_until,
        ) = self.service_period_from_logbook()
        self.save()

    def _unlink_logbook(self):
        LoggedHours.objects.filter(invoice_service__invoice=self).update(
            invoice_service=None, archived_at=None
        )
        LoggedCost.objects.filter(invoice_service__invoice=self).update(
            invoice_service=None, archived_at=None
        )

    def _unlink_down_payments(self):
        self.down_payment_invoices.update(down_payment_applied_to=None)

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.is_freezed:
            messages.error(request, _("Archived invoices cannot be deleted."))
            return False
        if instance.status > instance.IN_PREPARATION:
            messages.error(
                request, _("Invoices in preparation may be deleted, others not.")
            )
            return False
        return None

    def service_period_from_logbook(self):
        with connections["default"].cursor() as cursor:
            cursor.execute(
                """
with sq as (
    select min(rendered_on) as min_date, max(rendered_on) as max_date
    from logbook_loggedhours log
    left join invoices_service i_s on log.invoice_service_id=i_s.id
    where i_s.invoice_id=%s

    union all

    select min(rendered_on) as min_date, max(rendered_on) as max_date
    from logbook_loggedcost log
    left join invoices_service i_s on log.invoice_service_id=i_s.id
    where i_s.invoice_id=%s
)
select min(min_date), max(max_date) from sq
                """,
                [self.id, self.id],
            )
            return next(iter(cursor))

    @property
    def service_period(self):
        period = [self.service_period_from, self.service_period_until]
        return (
            "{} - {}".format(*tuple(local_date_format(day) for day in period))
            if all(period)
            else None
        )


@model_urls
class Service(ServiceBase):
    RELATED_MODEL_FIELD = "invoice"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("invoice"),
    )
    project_service = models.ForeignKey(
        "projects.Service",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="invoice_services",
        verbose_name=_("project service"),
    )
    # Invoicing the offer links the entries logged so far too, the lines
    # don't say where they come from otherwise
    from_offer = models.BooleanField(
        _("invoiced from the offer"), default=False, editable=False
    )

    def get_absolute_url(self):
        return self.invoice.get_absolute_url()

    @classmethod
    def allow_update(cls, instance, request):
        if instance.invoice.status > instance.invoice.IN_PREPARATION:
            messages.error(
                request,
                _(
                    "Cannot modify a service bound to an invoice"
                    " which is not in preparation anymore."
                ),
            )
            return False
        return True

    allow_delete = allow_update

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return instance.get_absolute_url() if instance else "invoices_invoice_list"
        return None

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        period = invoice.service_period_from_logbook()

        self.loggedhours_set.update(invoice_service=None, archived_at=None)
        self.loggedcost_set.update(invoice_service=None, archived_at=None)

        super().delete(*args, **kwargs)

        invoice.save()  # Recalculate total

        # The service period may have been changed by hand, don't change it
        # silently (shown by the generic delete view)
        if (new_period := invoice.service_period_from_logbook()) != period and all(
            new_period
        ):
            self.delete_warnings = [
                _(
                    "The logged hours and costs of this invoice now cover the"
                    " service period %(period)s. Update the invoice's service"
                    " period if necessary."
                )
                % {"period": " - ".join(local_date_format(day) for day in new_period)}
            ]

    delete.alters_data = True


def service_surplus(project_service, *, logbook_cutoff_date=None):
    """Logged hours (for invoicing), costs and third party costs of a service
    beyond what its lines on invoices which aren't cancelled contain, e.g.
    after invoicing the offer and working more than offered

    At most what hasn't been invoiced from the logbook yet: work logged
    before invoicing the offer belongs to the offered amount, also if it was
    more than offered."""
    hours = project_service.loggedhours.order_by()
    costs = project_service.loggedcosts.order_by()
    if logbook_cutoff_date:
        hours = hours.filter(rendered_on__lte=logbook_cutoff_date)
        costs = costs.filter(rendered_on__lte=logbook_cutoff_date)

    def logged(hours, costs):
        return {
            key: value or Z2
            for key, value in (
                hours.aggregate(hours=Sum(HOURS_FOR_INVOICING))
                | costs.aggregate(
                    cost=Sum("cost"), third_party_costs=Sum("third_party_costs")
                )
            ).items()
        }

    total = logged(hours, costs)
    not_archived = logged(
        hours.filter(archived_at__isnull=True), costs.filter(archived_at__isnull=True)
    )
    invoiced = (
        Service.objects
        .filter(project_service=project_service)
        .exclude(invoice__status=Invoice.CANCELED)
        .aggregate(
            hours=Sum("effort_hours"),
            cost=Sum("cost"),
            third_party_costs=Sum("third_party_costs"),
        )
    )
    return {
        key: max(
            min(not_archived[key], total[key] - (invoiced[key] or Z2)), Z2
        ).quantize(zero)
        for key, zero in [("hours", Z1), ("cost", Z2), ("third_party_costs", Z2)]
    }


class RecurringInvoiceQuerySet(SearchQuerySet):
    def renewal_candidates(self):
        today = dt.date.today()
        return (
            self
            .annotate(_start=Coalesce("next_period_starts_on", "starts_on"))
            .filter(
                Q(_start__lte=today - F("create_invoice_on_day")),
                Q(ends_on__isnull=True) | Q(ends_on__gte=F("_start")),
            )
            .select_related("customer", "contact", "owned_by")
        )

    def open(self):
        return self.filter(Q(ends_on__isnull=True) | Q(ends_on__gte=dt.date.today()))

    def closed(self):
        return self.filter(Q(ends_on__isnull=False) & Q(ends_on__lt=dt.date.today()))

    def maybe_actionable(self):
        return self.open().filter(owned_by__is_active=False)


@model_urls
class RecurringInvoice(ModelWithTotal):
    PERIODICITY_CHOICES = [
        ("yearly", _("yearly")),
        ("quarterly", _("quarterly")),
        ("monthly", _("monthly")),
        ("weekly", _("weekly")),
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
        User, on_delete=models.PROTECT, verbose_name=_("contact person")
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)

    third_party_costs = MoneyField(
        _("third party costs"),
        default=Z2,
        help_text=_("Only used for statistical purposes."),
    )
    postal_address = models.TextField(_("postal address"))

    @property
    def tax_rate(self):
        """Recurring invoices have no tax rate of their own (the attribute
        removes the field of ``ModelWithTotal``), they and their invoices use
        the current one"""
        return default_tax_rate()

    starts_on = models.DateField(_("starts on"), default=dt.date.today)
    ends_on = models.DateField(_("cancel the auto-renewal on"), blank=True, null=True)
    periodicity = models.CharField(
        _("periodicity"), max_length=20, choices=PERIODICITY_CHOICES
    )
    create_invoice_on_day = models.IntegerField(
        _("create invoice on day"),
        default=-20,
        help_text=_(
            "Invoices are created 20 days before their period begins by default."
        ),
    )
    next_period_starts_on = models.DateField(
        _("next period starts on"), blank=True, null=True
    )

    create_project = models.BooleanField(
        _("Create project?"),
        help_text=_("Invoices are created without projects by default."),
        default=False,
    )
    PREPARE = "prepare"
    MARK_AS_SENT = "mark_as_sent"
    SEND = "send"
    NEW_INVOICES_CHOICES = [
        (PREPARE, _("Create them in preparation")),
        (
            MARK_AS_SENT,
            _("Create them and mark them as sent (if they are sent another way)"),
        ),
        (SEND, _("Send them by email automatically")),
    ]
    new_invoices = models.CharField(
        _("new invoices"),
        max_length=20,
        choices=NEW_INVOICES_CHOICES,
        default=PREPARE,
        help_text=_(
            "New invoices which would be dated on or before the freeze date"
            " are dated the day after it."
        ),
    )
    send_to = models.EmailField(
        _("recipient"),
        blank=True,
        help_text=_(
            "Proposed: the accounts payable address of the organization, the"
            " contact or the central address. The owner gets a copy and the"
            " replies."
        ),
    )
    mail_subject = models.CharField(_("subject"), max_length=200, blank=True)
    mail_body = models.TextField(
        _("text"),
        blank=True,
        help_text=_(
            "{code}, {total}, {due_on} and {service_period} are replaced with"
            " the values of each invoice."
        ),
    )

    objects = RecurringInvoiceQuerySet.as_manager()

    class Meta:
        ordering = ["customer__name", "title"]
        verbose_name = _("recurring invoice")
        verbose_name_plural = _("recurring invoices")

    def __str__(self):
        return f"{self.title} - {self.owned_by.get_short_name()}"

    def __html__(self):
        return format_html("{} - {}", self.title, self.owned_by.get_short_name())

    @property
    def pretty_status(self):
        if self.ends_on:
            return _("%(periodicity)s from %(from)s until %(until)s") % {
                "periodicity": self.get_periodicity_display(),
                "from": local_date_format(self.starts_on),
                "until": local_date_format(self.ends_on),
            }
        return _("%(periodicity)s from %(from)s") % {
            "periodicity": self.get_periodicity_display(),
            "from": local_date_format(self.starts_on),
        }

    @property
    def pretty_next_period(self):
        start = self.next_period_starts_on or self.starts_on
        if self.ends_on and self.ends_on < start:
            return ""
        create = start + dt.timedelta(days=self.create_invoice_on_day)

        return _(
            "Next period starts on %(start)s, invoice will be created on %(create)s"
        ) % {"start": local_date_format(start), "create": local_date_format(create)}

    @property
    def status_badge(self):
        return format_html(
            '<span class="badge text-bg-{}">{}</span>',
            "light" if self.ends_on else "secondary",
            self.pretty_status,
        )

    def create_single_invoice(self, *, period_starts_on, period_ends_on):
        project = None
        if self.create_project:
            project = Project.objects.create(
                customer=self.customer,
                contact=self.contact,
                title=self.title,
                description=self.description,
                owned_by=self.owned_by,
                type=Project.MAINTENANCE,
            )

        # Not in the frozen period, invoices couldn't be sent anymore
        invoiced_on = max(
            period_starts_on, FreezeDate.objects.up_to() + dt.timedelta(days=1)
        )

        return Invoice.objects.create(
            customer=self.customer,
            contact=self.contact,
            project=project,
            invoiced_on=invoiced_on,
            due_on=invoiced_on + dt.timedelta(days=15),
            title=self.title,
            description=self.description,
            service_period_from=period_starts_on,
            service_period_until=period_ends_on,
            owned_by=self.owned_by,
            # Invoices which are sent by email stay in preparation until the
            # mail has been sent, see create_invoices()
            status=Invoice.SENT
            if self.new_invoices == self.MARK_AS_SENT
            else Invoice.IN_PREPARATION,
            type=Invoice.DOWN_PAYMENT if self.create_project else Invoice.FIXED,
            postal_address=self.postal_address,
            subtotal=self.subtotal,
            discount=self.discount,
            liable_to_vat=self.liable_to_vat,
            third_party_costs=self.third_party_costs,
        )

    def pending_periods(self):
        """The periods ``(starts_on, ends_on)`` whose invoices are due to be
        created now"""
        periods = []
        days = recurring(
            max(filter(None, (self.next_period_starts_on, self.starts_on))),
            self.periodicity,
        )
        generate_until = min(
            filter(None, (in_days(-self.create_invoice_on_day), self.ends_on))
        )
        this_period = next(days)
        while this_period <= generate_until:
            next_period = next(days)
            periods.append((this_period, next_period - dt.timedelta(days=1)))
            this_period = next_period
        return periods

    def create_invoices(self):
        from workbench.invoices.sending import send_automatically

        invoices = []
        for starts_on, ends_on in self.pending_periods():
            invoice = self.create_single_invoice(
                period_starts_on=starts_on, period_ends_on=ends_on
            )
            if self.new_invoices == self.SEND:
                send_automatically(invoice, self)
            invoices.append(invoice)
            self.next_period_starts_on = ends_on + dt.timedelta(days=1)
        self.save()
        return invoices


class ProjectedInvoice(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="projected_invoices",
        verbose_name=_("project"),
    )
    invoiced_on = models.DateField(_("invoiced on"))
    gross_margin = MoneyField(
        _("gross margin"),
        help_text=_("Invoice total excl. tax minus third party costs incl. tax."),
    )
    description = models.CharField(_("description"), max_length=200, blank=True)

    class Meta:
        ordering = ["invoiced_on"]
        verbose_name = _("projected gross margin")
        verbose_name_plural = _("projected gross margin")

    def __str__(self):
        return f"{local_date_format(self.invoiced_on)}: {currency(self.gross_margin)}"
