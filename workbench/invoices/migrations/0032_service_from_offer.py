from django.db import migrations, models
from django.db.models import Sum
from django.db.models.functions import Coalesce


def backfill(apps, schema_editor):
    """Lines without linked logbook entries come from the offer: invoicing
    the logbook only creates lines when there's something to invoice. Lines
    with linked entries come from the offer if they still have the offered
    hours and cost and don't sum up their entries; otherwise they come from
    the logbook (lines are often edited after invoicing the logbook)."""
    Service = apps.get_model("invoices", "Service")
    LoggedHours = apps.get_model("logbook", "LoggedHours")
    LoggedCost = apps.get_model("logbook", "LoggedCost")

    hours = dict(
        LoggedHours.objects
        .filter(invoice_service__isnull=False)
        .order_by()
        .values("invoice_service")
        .annotate(sum=Sum(Coalesce("hours_for_invoicing", "hours")))
        .values_list("invoice_service", "sum")
    )
    costs = dict(
        LoggedCost.objects
        .filter(invoice_service__isnull=False)
        .order_by()
        .values("invoice_service")
        .annotate(sum=Sum("cost"))
        .values_list("invoice_service", "sum")
    )

    def amounts(effort_hours, cost):
        return (effort_hours or 0, cost or 0)

    from_offer = [
        line.pk
        for line in Service.objects
        .filter(project_service__isnull=False)
        .select_related("project_service")
        .only(
            "effort_hours",
            "cost",
            "project_service__effort_hours",
            "project_service__cost",
        )
        if (line.pk not in hours and line.pk not in costs)
        or (
            amounts(line.effort_hours, line.cost)
            == amounts(line.project_service.effort_hours, line.project_service.cost)
            != amounts(hours.get(line.pk), costs.get(line.pk))
        )
    ]
    Service.objects.filter(pk__in=from_offer).update(from_offer=True)


class Migration(migrations.Migration):
    dependencies = [
        ("invoices", "0031_recurringinvoice_mark_as_sent"),
        ("logbook", "0024_rename_hours_for_invoicing"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="from_offer",
            field=models.BooleanField(
                default=False, editable=False, verbose_name="invoiced from the offer"
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
