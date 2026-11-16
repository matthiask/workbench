from collections import defaultdict

from django.db import migrations


def link_recurring_invoices(apps, schema_editor):
    """Link invoices created by recurring invoices: same customer and title,
    service period starting within the periods created so far. Invoices
    matching several recurring invoices are only linked if exactly one of
    them has the same subtotal."""
    Invoice = apps.get_model("invoices", "Invoice")
    RecurringInvoice = apps.get_model("invoices", "RecurringInvoice")

    candidates = defaultdict(list)
    for recurring in RecurringInvoice.objects.filter(
        next_period_starts_on__isnull=False
    ):
        invoices = Invoice.objects.filter(
            recurring_invoice__isnull=True,
            customer_id=recurring.customer_id,
            title=recurring.title,
            service_period_from__gte=recurring.starts_on,
            service_period_from__lt=recurring.next_period_starts_on,
        )
        if recurring.ends_on:
            invoices = invoices.filter(service_period_from__lte=recurring.ends_on)
        for invoice in invoices:
            candidates[invoice].append(recurring)

    for invoice, recurrings in candidates.items():
        matches = (
            recurrings
            if len(recurrings) == 1
            else [r for r in recurrings if r.subtotal == invoice.subtotal]
        )
        if len(matches) == 1:
            invoice.recurring_invoice = matches[0]
            invoice.save(update_fields=["recurring_invoice"])


class Migration(migrations.Migration):
    dependencies = [
        ("invoices", "0040_invoice_recurring_invoice"),
    ]

    operations = [
        migrations.RunPython(link_recurring_invoices, migrations.RunPython.noop),
    ]
