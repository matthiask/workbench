from datetime import date, timedelta

from django.contrib import messages
from django.db import models
from django.db.models import F, Q, Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.invoices.utils import recurring
from workbench.projects.models import Project
from workbench.services.models import ServiceBase
from workbench.tools.formats import local_date_format
from workbench.tools.models import ModelWithTotal, MoneyField, SearchQuerySet, Z
from workbench.tools.urls import model_urls
from workbench.tools.validation import raise_if_errors


class InvoiceQuerySet(SearchQuerySet):
    def valid(self):
        return self.filter(
            status__in=(Invoice.IN_PREPARATION, Invoice.SENT, Invoice.PAID)
        )


@model_urls
class Invoice(ModelWithTotal):
    IN_PREPARATION = 10
    SENT = 20
    PAID = 40
    CANCELED = 50
    REPLACED = 60

    STATUS_CHOICES = (
        (IN_PREPARATION, _("In preparation")),
        (SENT, _("Sent")),
        (PAID, _("Paid")),
        (CANCELED, _("Canceled")),
        (REPLACED, _("Replaced")),
    )

    FIXED = "fixed"
    DOWN_PAYMENT = "down-payment"
    SERVICES = "services"

    TYPE_CHOICES = (
        (FIXED, _("Fixed amount")),
        (DOWN_PAYMENT, _("Down payment")),
        (SERVICES, _("Services")),
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
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("owned by"), related_name="+"
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
    down_payment_total = MoneyField(_("down payment total"), default=Z)
    third_party_costs = MoneyField(
        _("third party costs"),
        default=Z,
        help_text=_("Only used for statistical purposes."),
    )

    postal_address = models.TextField(_("postal address"), blank=True)
    _code = models.IntegerField(_("code"))

    payment_notice = models.TextField(_("payment notice"), blank=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_status = self.status

    def __str__(self):
        return "%s %s %s" % (self.code, self.title, self.owned_by.get_short_name())

    def __html__(self):
        return format_html(
            "<small>{}</small> {} - {}",
            self.code,
            self.title,
            self.owned_by.get_short_name(),
        )

    def save(self, *args, **kwargs):
        new = False
        if not self.pk:
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
            new = True
        super().save(*args, **kwargs)
        if new:
            self.refresh_from_db()

    save.alters_data = True

    def _calculate_total(self):
        if self.type == self.SERVICES:
            self.subtotal = sum(
                (service.service_cost for service in self.services.all()), Z
            )
        super()._calculate_total()

    @property
    def code(self):
        return (
            "%s-%04d" % (self.project.code, self._code)
            if self.project
            else "%05d" % self._code
        )

    @property
    def total_excl_tax(self):
        return self.subtotal - self.discount - self.down_payment_total

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}

        if self.status >= self.SENT:
            if not self.invoiced_on or not self.due_on:
                errors["status"] = _(
                    "Invoice and/or due date missing for selected state."
                )

        if self.invoiced_on and self.due_on:
            if self.invoiced_on > self.due_on:
                errors["due_on"] = _("Due date has to be after invoice date.")

        if self.type in (self.SERVICES, self.DOWN_PAYMENT) and not self.project:
            errors["__all__"] = _("Invoices of type %(type)s require a project.") % {
                "type": self.get_type_display()
            }
        raise_if_errors(errors, exclude)

    @property
    def pretty_status(self):
        d = {
            "invoiced_on": (
                local_date_format(self.invoiced_on, "d.m.Y")
                if self.invoiced_on
                else None
            ),
            "reminded_on": (
                local_date_format(self.last_reminded_on, "d.m.Y")
                if self.last_reminded_on
                else None
            ),
            "created_at": local_date_format(self.created_at, "d.m.Y"),
            "closed_on": (
                local_date_format(self.closed_on, "d.m.Y") if self.closed_on else None
            ),
        }

        if self.status == self.IN_PREPARATION:
            return _("In preparation since %(created_at)s") % d
        elif self.status == self.SENT:
            if self.last_reminded_on:
                return _("Sent on %(invoiced_on)s, reminded on %(reminded_on)s") % d

            if self.due_on and date.today() > self.due_on:
                return _("Sent on %(invoiced_on)s but overdue") % d

            return _("Sent on %(invoiced_on)s") % d
        elif self.status == self.PAID:
            return _("Paid on %(closed_on)s") % d
        else:
            return self.get_status_display()

    @property
    def status_css(self):
        if self.status == self.SENT:
            if self.last_reminded_on or (self.due_on and date.today() > self.due_on):
                return "warning"

        return {
            self.IN_PREPARATION: "info",
            self.SENT: "success",
            self.PAID: "default",
            self.CANCELED: "danger",
            self.REPLACED: "",
        }[self.status]

    @property
    def total_title(self):
        if self.type == self.DOWN_PAYMENT:
            return (
                _("down payment total CHF incl. tax")
                if self.liable_to_vat
                else _("down payment total CHF")
            )
        else:
            return _("total CHF incl. tax") if self.liable_to_vat else _("total CHF")

    def create_services_from_logbook(self, project_services):
        assert self.project, "cannot call create_services_from_logbook without project"

        for ps in project_services:
            not_archived_effort = ps.loggedhours.filter(
                archived_at__isnull=True
            ).order_by()
            not_archived_costs = ps.loggedcosts.filter(
                archived_at__isnull=True
            ).order_by()

            hours = not_archived_effort.aggregate(Sum("hours"))["hours__sum"] or Z
            cost = not_archived_costs.aggregate(Sum("cost"))["cost__sum"] or Z

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

        self.save()

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.status > instance.IN_PREPARATION:
            messages.error(
                request, _("Invoices in preparation may be deleted, others not.")
            )
            return False
        return None


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


class RecurringInvoiceQuerySet(SearchQuerySet):
    def create_invoices(self):
        generate_until = date.today() + timedelta(days=20)
        invoices = []
        for ri in self.filter(
            Q(starts_on__lte=generate_until),
            Q(ends_on__isnull=True)
            | Q(next_period_starts_on__isnull=True)
            | Q(ends_on__gte=F("next_period_starts_on")),
            Q(next_period_starts_on__isnull=True)
            | Q(next_period_starts_on__lte=generate_until),
        ).select_related("customer", "contact", "owned_by"):
            invoices.extend(ri.create_invoices(generate_until=generate_until))
        return invoices


@model_urls
class RecurringInvoice(ModelWithTotal):
    PERIODICITY_CHOICES = [
        ("yearly", _("yearly")),
        ("quarterly", _("quarterly")),
        ("monthly", _("monthly")),
        ("weekly", _("weekly")),
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

    created_at = models.DateTimeField(_("created at"), default=timezone.now)

    third_party_costs = MoneyField(
        _("third party costs"),
        default=Z,
        help_text=_("Only used for statistical purposes."),
    )
    postal_address = models.TextField(_("postal address"), blank=True)

    starts_on = models.DateField(_("starts on"), default=date.today)
    ends_on = models.DateField(_("ends on"), blank=True, null=True)
    periodicity = models.CharField(
        _("periodicity"), max_length=20, choices=PERIODICITY_CHOICES
    )
    next_period_starts_on = models.DateField(
        _("next period starts on"), blank=True, null=True
    )

    objects = RecurringInvoiceQuerySet.as_manager()

    class Meta:
        ordering = ["customer__name", "title"]
        verbose_name = _("recurring invoice")
        verbose_name_plural = _("recurring invoices")

    def __str__(self):
        return self.title

    @property
    def pretty_periodicity(self):
        if self.ends_on:
            return _("%(periodicity)s from %(from)s until %(until)s") % {
                "periodicity": self.get_periodicity_display(),
                "from": local_date_format(self.starts_on, "d.m.Y"),
                "until": local_date_format(self.ends_on, "d.m.Y"),
            }
        return _("%(periodicity)s from %(from)s") % {
            "periodicity": self.get_periodicity_display(),
            "from": local_date_format(self.starts_on, "d.m.Y"),
        }

    def create_single_invoice(self, *, period_starts_on, period_ends_on):
        return Invoice.objects.create(
            customer=self.customer,
            contact=self.contact,
            project=None,
            invoiced_on=period_starts_on,
            due_on=period_starts_on + timedelta(days=15),
            title=self.title,
            description="\n\n".join(
                filter(
                    None,
                    (
                        self.description,
                        "{}: {} - {}".format(
                            _("Period"),
                            local_date_format(period_starts_on, "d.m.Y"),
                            local_date_format(period_ends_on, "d.m.Y"),
                        ),
                    ),
                )
            ),
            owned_by=self.owned_by,
            status=Invoice.IN_PREPARATION,
            type=Invoice.FIXED,
            postal_address=self.postal_address,
            subtotal=self.subtotal,
            discount=self.discount,
            liable_to_vat=self.liable_to_vat,
            # tax_rate=self.tax_rate,
            # total=self.total,
            third_party_costs=self.third_party_costs,
        )

    def create_invoices(self, *, generate_until):
        invoices = []
        days = recurring(
            max(filter(None, (self.next_period_starts_on, self.starts_on))),
            self.periodicity,
        )
        generate_until = min(filter(None, (generate_until, self.ends_on)))
        this_period = next(days)
        while True:
            if this_period > generate_until:
                break
            next_period = next(days)
            invoices.append(
                self.create_single_invoice(
                    period_starts_on=this_period,
                    period_ends_on=next_period - timedelta(days=1),
                )
            )
            self.next_period_starts_on = next_period
            this_period = next_period
        self.save()
        return invoices
