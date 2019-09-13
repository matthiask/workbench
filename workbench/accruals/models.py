from decimal import Decimal

from django.contrib import messages
from django.db import models
from django.db.models import F, Q, Sum
from django.utils.translation import gettext_lazy as _

from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.models import Project
from workbench.tools.formats import local_date_format
from workbench.tools.models import Model, MoneyField, Z
from workbench.tools.urls import model_urls


@model_urls
class CutoffDate(Model):
    day = models.DateField(_("cutoff date"), unique=True)

    class Meta:
        ordering = ["-day"]
        verbose_name = _("cutoff date")
        verbose_name_plural = _("cutoff dates")

    def __str__(self):
        return local_date_format(self.day)

    @classmethod
    def allow_update(cls, instance, request):
        if Accrual.objects.filter(cutoff_date=instance.day).exists():
            messages.error(
                request,
                _("Cannot modify a cutoff date where accrual records already exist."),
            )
            return False
        return True

    @classmethod
    def allow_delete(cls, instance, request):
        if Accrual.objects.filter(cutoff_date=instance.day).exists():
            messages.error(
                request,
                _("Cannot modify a cutoff date where accrual records already exist."),
            )
            return False
        return super().allow_delete(instance, request)


class AccrualQuerySet(models.QuerySet):
    def generate_accruals(self, *, cutoff_date):
        # month = dt.date.today().replace(day=1)

        down_payment_invoices = Invoice.objects.valid().filter(
            project__isnull=False,
            project__in=Project.objects.filter(
                Q(closed_on__isnull=True) | Q(closed_on__gt=cutoff_date)
            ),
            invoiced_on__lte=cutoff_date,
            type=Invoice.DOWN_PAYMENT,
        )
        projects = {invoice.project_id for invoice in down_payment_invoices}
        logged_costs_effort = {
            row["service__project"]: row["_cost"]
            for row in LoggedHours.objects.filter(
                service__project__in=projects,
                service__effort_rate__isnull=False,
                rendered_on__lte=cutoff_date,
            )
            .order_by()
            .values("service__project")
            .annotate(_cost=Sum(F("hours") * F("service__effort_rate")))
        }
        logged_costs_cost = {
            row["project"]: row["cost__sum"]
            for row in LoggedCost.objects.filter(
                project__in=projects, rendered_on__lte=cutoff_date
            )
            .order_by()
            .values("project")
            .annotate(Sum("cost"))
        }

        logged = {
            project: logged_costs_effort.get(project, Z)
            + logged_costs_cost.get(project, Z)
            for project in projects
        }
        remaining = dict(logged)

        for invoice in (
            Invoice.objects.valid()
            .filter(
                project__isnull=False,
                project__in=projects,
                invoiced_on__lte=cutoff_date,
                subtotal__gt=0,
            )
            .order_by("invoiced_on")
        ):
            if invoice.type == invoice.DOWN_PAYMENT:
                work_progress = (
                    100 * remaining[invoice.project_id] / invoice.total_excl_tax
                )
                work_progress = min(100, max(0, work_progress))
                self.get_or_create(
                    invoice=invoice,
                    cutoff_date=cutoff_date,
                    defaults={
                        "work_progress": work_progress,
                        "logbook": logged[invoice.project_id],
                    },
                )

            remaining[invoice.project_id] -= invoice.total_excl_tax


@model_urls
class Accrual(Model):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, verbose_name=_("invoice")
    )
    cutoff_date = models.DateField(_("cutoff date"))
    work_progress = models.IntegerField(
        _("work progress"),
        help_text=_(
            "Percentage of down payment invoice for which the work has"
            " already been done."
        ),
    )
    logbook = MoneyField(_("logbook"))

    objects = AccrualQuerySet.as_manager()

    class Meta:
        ordering = ["-cutoff_date", "-invoice__project__code", "-invoice__code"]
        unique_together = [("invoice", "cutoff_date")]
        verbose_name = _("accrual")
        verbose_name_plural = _("accruals")

    def __str__(self):
        return str(self.invoice)

    @property
    def accrual(self):
        return self.invoice.total_excl_tax * (Decimal(100) - self.work_progress) / 100
