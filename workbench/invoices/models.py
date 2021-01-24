import datetime as dt

from django.conf import settings
from django.contrib import messages
from django.db import connections, models
from django.db.models import F, Q, Sum
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction
from workbench.contacts.models import Organization, Person
from workbench.invoices.utils import recurring
from workbench.projects.models import Project
from workbench.services.models import ServiceBase
from workbench.tools.formats import Z1, Z2, local_date_format
from workbench.tools.models import ModelWithTotal, MoneyField, SearchQuerySet
from workbench.tools.urls import model_urls
from workbench.tools.validation import in_days, raise_if_errors


class InvoiceQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(status__in=(Invoice.IN_PREPARATION, Invoice.SENT))

    def invoiced(self):
        return self.filter(status__in=Invoice.INVOICED_STATUSES)

    def overdue(self):
        return self.filter(
            status=Invoice.SENT, due_on__isnull=False, due_on__lte=in_days(-15)
        )


@model_urls
class Invoice(ModelWithTotal):
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

    TYPE_CHOICES = (
        (FIXED, _("Fixed amount")),
        (DOWN_PAYMENT, _("Down payment")),
        (SERVICES, _("Services")),
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

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    service_period_from = models.DateField(
        _("service period from"), blank=True, null=True
    )
    service_period_until = models.DateField(
        _("service period until"), blank=True, null=True
    )
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("responsible")
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
        help_text=_("This fields' value is overridden when processing credit entries."),
    )

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_status = self.status

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

        self._fts = " ".join(
            str(part)
            for part in [
                self.code,
                self.customer.name,
                self.contact.full_name if self.contact else "",
                self.project.title if self.project else "",
            ]
        )
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

    save.alters_data = True

    def delete(self, *args, **kwargs):
        assert (
            self.status <= self.IN_PREPARATION
        ), "Trying to delete an invoice not in preparation"
        super().delete(*args, **kwargs)

    delete.alters_data = True

    def _calculate_total(self):
        if self.type == self.SERVICES:
            services = self.services.all()
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

        if self.status >= self.SENT:
            if not self.invoiced_on or not self.due_on:
                errors["status"] = _(
                    "Invoice and/or due date missing for selected state."
                )

        if self.status <= self.SENT and self.closed_on:
            errors["status"] = _("Invalid status when closed on is already set.")

        if self.invoiced_on and self.due_on:
            if self.invoiced_on > self.due_on:
                errors["due_on"] = _("Due date has to be after invoice date.")

        if self.type in (self.SERVICES, self.DOWN_PAYMENT) and not self.project:
            errors["__all__"] = _("Invoices of type %(type)s require a project.") % {
                "type": self.get_type_display()
            }

        if self.status == Invoice.CANCELED and not self.payment_notice:
            errors["payment_notice"] = _(
                "Please provide a short reason for the invoice cancellation."
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
    def pretty_status(self):
        d = {
            "invoiced_on": (
                local_date_format(self.invoiced_on) if self.invoiced_on else None
            ),
            "reminded_on": (
                local_date_format(self.last_reminded_on)
                if self.last_reminded_on
                else None
            ),
            "created_at": local_date_format(self.created_at.date()),
            "closed_on": (
                local_date_format(self.closed_on) if self.closed_on else None
            ),
        }

        if self.status == self.IN_PREPARATION:
            return _("In preparation since %(created_at)s") % d
        elif self.status == self.SENT:
            if self.last_reminded_on:
                return _("Sent on %(invoiced_on)s, reminded on %(reminded_on)s") % d

            if self.due_on and dt.date.today() > self.due_on:
                return _("Sent on %(invoiced_on)s but overdue") % d

            return _("Sent on %(invoiced_on)s") % d
        elif self.status == self.PAID:
            return _("Paid on %(closed_on)s") % d
        else:
            return self.get_status_display()

    def payment_reminders_sent_at(self):
        from workbench.tools.history import changes  # Avoid a circular import

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
            self.PAID: "default",
            self.CANCELED: "danger",
        }[self.status]

        if self.status == self.SENT:
            if self.last_reminded_on or (self.due_on and dt.date.today() > self.due_on):
                css = "warning"

        return format_html(
            '<span class="badge badge-{}">{}</span>', css, self.pretty_status
        )

    @property
    def total_title(self):
        if self.type == self.DOWN_PAYMENT:
            return (
                _("Down payment total %(currency)s incl. tax")
                if self.liable_to_vat
                else _("Down payment total %(currency)s")
            ) % {"currency": settings.WORKBENCH.CURRENCY}
        else:
            return (
                _("Total %(currency)s incl. tax")
                if self.liable_to_vat
                else _("Total %(currency)s")
            ) % {"currency": settings.WORKBENCH.CURRENCY}

    def create_services_from_logbook(self, project_services):
        assert self.project, "cannot call create_services_from_logbook without project"

        for ps in project_services:
            not_archived_effort = ps.loggedhours.filter(
                archived_at__isnull=True
            ).order_by()
            not_archived_costs = ps.loggedcosts.filter(
                archived_at__isnull=True
            ).order_by()

            hours = not_archived_effort.aggregate(Sum("hours"))["hours__sum"] or Z1
            cost = not_archived_costs.aggregate(Sum("cost"))["cost__sum"] or Z2

            if hours or cost:
                service = Service(
                    invoice=self,
                    project_service=ps,
                    title=ps.title,
                    description=ps.description,
                    position=ps.position,
                    effort_rate=ps.effort_rate,
                    effort_type=ps.effort_type,
                    effort_hours=hours,
                    cost=cost,
                    third_party_costs=not_archived_costs.filter(
                        third_party_costs__isnull=False
                    ).aggregate(Sum("third_party_costs"))["third_party_costs__sum"],
                )
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

    def create_services_from_offer(self, project_services):
        assert self.project, "cannot call create_services_from_offer without project"

        for ps in project_services:
            service = Service(
                invoice=self,
                project_service=ps,
                title=ps.title,
                description=ps.description,
                position=ps.position,
                effort_rate=ps.effort_rate,
                effort_type=ps.effort_type,
                effort_hours=ps.effort_hours,
                cost=ps.cost,
                third_party_costs=ps.third_party_costs,
            )
            service.save(skip_related_model=True)
            ps.loggedhours.filter(archived_at__isnull=True).update(
                invoice_service=service, archived_at=timezone.now()
            )
            ps.loggedcosts.filter(archived_at__isnull=True).update(
                invoice_service=service, archived_at=timezone.now()
            )

        (
            self.service_period_from,
            self.service_period_until,
        ) = self.service_period_from_logbook()
        self.save()

    @classmethod
    def allow_delete(cls, instance, request):
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
            return list(cursor)[0]

    @property
    def service_period(self):
        period = [self.service_period_from, self.service_period_until]
        return (
            "%s - %s" % tuple(local_date_format(day) for day in period)
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


class RecurringInvoiceQuerySet(SearchQuerySet):
    def renewal_candidates(self):
        today = dt.date.today()
        return (
            self.annotate(_start=Coalesce("next_period_starts_on", "starts_on"))
            .filter(
                Q(_start__lte=today - F("create_invoice_on_day")),
                Q(ends_on__isnull=True) | Q(ends_on__gte=F("_start")),
            )
            .select_related("customer", "contact", "owned_by")
        )


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
        User, on_delete=models.PROTECT, verbose_name=_("responsible")
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)

    third_party_costs = MoneyField(
        _("third party costs"),
        default=Z2,
        help_text=_("Only used for statistical purposes."),
    )
    postal_address = models.TextField(_("postal address"))

    starts_on = models.DateField(_("starts on"), default=dt.date.today)
    ends_on = models.DateField(_("ends on"), blank=True, null=True)
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

    objects = RecurringInvoiceQuerySet.as_manager()

    class Meta:
        ordering = ["customer__name", "title"]
        verbose_name = _("recurring invoice")
        verbose_name_plural = _("recurring invoices")

    def __str__(self):
        return self.title

    def __html__(self):
        return "%s - %s" % (self.title, self.owned_by.get_short_name())

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
            '<span class="badge badge-{}">{}</span>',
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

        return Invoice.objects.create(
            customer=self.customer,
            contact=self.contact,
            project=project,
            invoiced_on=period_starts_on,
            due_on=period_starts_on + dt.timedelta(days=15),
            title=self.title,
            description=self.description,
            service_period_from=period_starts_on,
            service_period_until=period_ends_on,
            owned_by=self.owned_by,
            status=Invoice.IN_PREPARATION,
            type=Invoice.DOWN_PAYMENT if self.create_project else Invoice.FIXED,
            postal_address=self.postal_address,
            subtotal=self.subtotal,
            discount=self.discount,
            liable_to_vat=self.liable_to_vat,
            # tax_rate=self.tax_rate,
            # total=self.total,
            third_party_costs=self.third_party_costs,
        )

    def create_invoices(self):
        invoices = []
        days = recurring(
            max(filter(None, (self.next_period_starts_on, self.starts_on))),
            self.periodicity,
        )
        generate_until = min(
            filter(None, (in_days(-self.create_invoice_on_day), self.ends_on))
        )
        this_period = next(days)
        while True:
            if this_period > generate_until:
                break
            next_period = next(days)
            invoices.append(
                self.create_single_invoice(
                    period_starts_on=this_period,
                    period_ends_on=next_period - dt.timedelta(days=1),
                )
            )
            self.next_period_starts_on = next_period
            this_period = next_period
        self.save()
        return invoices
