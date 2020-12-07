import datetime as dt
from decimal import Decimal

from django.contrib import messages
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.projects.models import Service
from workbench.tools.formats import hours_and_minutes
from workbench.tools.models import HoursField, Model, MoneyField, SearchQuerySet
from workbench.tools.urls import model_urls
from workbench.tools.validation import logbook_lock, raise_if_errors


@model_urls
class LoggedHours(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="loggedhours",
        verbose_name=_("service"),
    )
    created_at = models.DateTimeField(
        _("created at"), default=timezone.now, db_index=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("created by"),
        related_name="loggedhours_set",
    )
    rendered_on = models.DateField(
        _("rendered on"), default=dt.date.today, db_index=True
    )
    rendered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="loggedhours",
        verbose_name=_("rendered by"),
    )
    hours = HoursField(_("hours"), validators=[MinValueValidator(Decimal("0.1"))])
    description = models.TextField(_("description"))

    invoice_service = models.ForeignKey(
        "invoices.Service",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("invoice service"),
    )
    archived_at = models.DateTimeField(_("archived at"), blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["-rendered_on"])]
        ordering = ("-rendered_on", "-created_at")
        verbose_name = _("logged hours")
        verbose_name_plural = _("logged hours")

    def __str__(self):
        return "%s: %s" % (self.service.title, self.description)

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.invoice_service_id or instance.archived_at:
            messages.error(request, _("Cannot delete archived logged hours."))
            return False
        if instance.rendered_on < logbook_lock():
            messages.error(request, _("Cannot delete logged hours from past weeks."))
            return False
        return super().allow_delete(instance, request)

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return cls.urls["list"] + "?project={}".format(
                instance.service.project_id if instance else ""
            )


class LoggedCostQuerySet(SearchQuerySet):
    def expenses(self, *, user):
        return self.filter(are_expenses=True, rendered_by=user)


@model_urls
class LoggedCost(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="loggedcosts",
        verbose_name=_("service"),
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("created by")
    )
    rendered_on = models.DateField(
        _("rendered on"), default=dt.date.today, db_index=True
    )
    rendered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="loggedcosts",
        verbose_name=_("rendered by"),
    )
    cost = MoneyField(_("cost"))
    third_party_costs = MoneyField(
        _("third party costs"),
        blank=True,
        null=True,
        help_text=_("Total incl. tax for third-party services."),
    )
    description = models.TextField(_("description"))

    invoice_service = models.ForeignKey(
        "invoices.Service",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("invoice service"),
    )
    archived_at = models.DateTimeField(_("archived at"), blank=True, null=True)

    are_expenses = models.BooleanField(_("paid from my own pocket"), default=False)
    expense_report = models.ForeignKey(
        "expenses.ExpenseReport",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("expense report"),
        related_name="expenses",
    )

    expense_currency = models.CharField(
        _("original currency"), max_length=3, blank=True
    )
    expense_cost = MoneyField(_("original cost"), blank=True, null=True)

    objects = LoggedCostQuerySet.as_manager()

    class Meta:
        ordering = ("-rendered_on", "-created_at")
        verbose_name = _("logged cost")
        verbose_name_plural = _("logged costs")

    def __str__(self):
        return self.description

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.invoice_service_id or instance.archived_at:
            messages.error(request, _("Cannot delete archived logged cost entries."))
            return False
        if instance.expense_report:
            messages.error(
                request,
                _("Expenses are part of an expense report, cannot delete entry."),
            )
        return super().allow_delete(instance, request)

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return cls.urls["list"] + "?project={}".format(
                instance.service.project_id if instance else ""
            )

    def clean_fields(self, exclude):
        super().clean_fields(exclude)
        errors = {}
        expense = (self.expense_currency != "", self.expense_cost is not None)
        if any(expense) and not all(expense):
            if self.expense_currency == "":
                errors["expense_currency"] = _("Either fill in all fields or none.")
            if self.expense_cost is None:
                errors["expense_cost"] = _("Either fill in all fields or none.")
        raise_if_errors(errors, exclude)


@model_urls
class Break(Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_("user"), related_name="breaks"
    )
    starts_at = models.DateTimeField(_("starts at"))
    ends_at = models.DateTimeField(_("ends at"))

    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["-starts_at"]
        verbose_name = _("break")
        verbose_name_plural = _("breaks")

    def __str__(self):
        parts = [
            hours_and_minutes(self.timedelta.total_seconds()),
            self.description,
        ]
        return " ".join(filter(None, parts))

    @property
    def timedelta(self):
        return self.ends_at - self.starts_at

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        errors = {}
        if self.starts_at and self.ends_at:

            if self.starts_at.date() != self.ends_at.date():
                errors["ends_at"] = _("Breaks must start and end on the same day.")

            if self.starts_at >= self.ends_at:
                errors["ends_at"] = _("Breaks should end later than they begin.")

        raise_if_errors(errors, exclude)

    @classmethod
    def allow_update(cls, instance, request):
        if instance.user == request.user:
            return True
        messages.error(request, _("Cannot modify breaks of other users."))
        return False

    allow_delete = allow_update
