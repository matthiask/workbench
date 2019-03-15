from datetime import date

from django.db import models
from django.db.models import F, Q, Sum
from django.utils.translation import gettext_lazy as _

from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.models import Project
from workbench.tools.models import Model, Z
from workbench.tools.urls import model_urls


class AccrualQuerySet(models.QuerySet):
    def generate_accruals(self):
        month = date.today().replace(day=1)

        down_payment_invoices = Invoice.objects.valid().filter(
            project__isnull=False,
            project__in=Project.objects.filter(
                Q(closed_on__isnull=True) | Q(closed_on__gte=month)
            ),
            invoiced_on__lt=month,
            type=Invoice.DOWN_PAYMENT,
        )
        projects = {invoice.project_id for invoice in down_payment_invoices}
        logged_costs_effort = {
            row["service__project"]: row["_cost"]
            for row in LoggedHours.objects.filter(
                service__project__in=projects, service__effort_rate__isnull=False
            )
            .order_by()
            .values("service__project")
            .annotate(_cost=F("hours") * F("service__effort_rate"))
        }
        logged_costs_cost = {
            row["project"]: row["cost__sum"]
            for row in LoggedCost.objects.filter(project__in=projects)
            .order_by()
            .values("project")
            .annotate(Sum("cost"))
        }

        logged = {
            project: logged_costs_effort.get(project, Z)
            + logged_costs_cost.get(project, Z)
            for project in projects
        }

        for invoice in Invoice.objects.valid().filter(
            project__isnull=False,
            project__in=Project.objects.filter(
                Q(closed_on__isnull=True) | Q(closed_on__gte=month)
            ),
            invoiced_on__lt=month,
            type=Invoice.DOWN_PAYMENT,
            subtotal__gt=0,
        ):
            accrual = logged[invoice.project_id] / invoice.total_excl_tax
            self.get_or_create(
                invoice=invoice, month=month, defaults={"accrual": accrual}
            )


@model_urls()
class Accrual(Model):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="+", verbose_name=_("invoice")
    )
    month = models.DateField(_("month"))
    accrual = models.IntegerField(
        _("accrual"),
        help_text=_(
            "Percentage of down payment invoice for which the work has"
            " already been done."
        ),
    )

    objects = AccrualQuerySet.as_manager()

    class Meta:
        ordering = ["-month", "-invoice_id"]
        verbose_name = _("accrual")
        verbose_name_plural = _("accruals")

    def __str__(self):
        return str(self.invoice)

    def save(self, *args, **kwargs):
        self.month = self.month.replace(day=1)
        super().save(*args, **kwargs)

    save.alters_data = True
