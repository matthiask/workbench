import datetime as dt
from collections import defaultdict
from itertools import pairwise, takewhile

from django.db import migrations
from django.db.models import Q

from workbench.invoices.utils import recurring as recurring_days


def link_recurring_invoices(apps, schema_editor):
    """Link invoices created by recurring invoices before invoices remembered
    them. Generous, the link is only informational. Invoices of the same
    customer which

    - have the same title and start in the periods created so far,
    - cover exactly one of these periods (titles and amounts may have been
      edited), or
    - have the same title and subtotal and start before the next period (the
      service period may have been edited).

    Invoices matching several recurring invoices go to the one with the same
    title, then the same subtotal, then the one in whose periods they are;
    if that's still ambiguous they stay unlinked."""
    Invoice = apps.get_model("invoices", "Invoice")
    RecurringInvoice = apps.get_model("invoices", "RecurringInvoice")

    candidates = defaultdict(dict)  # invoice: {recurring: score}
    for recurring in RecurringInvoice.objects.filter(
        next_period_starts_on__isnull=False
    ):
        days = takewhile(
            lambda day, until=recurring.next_period_starts_on: day <= until,
            recurring_days(recurring.starts_on, recurring.periodicity),
        )
        periods = Q(pk__in=[])
        for starts_on, next_starts_on in pairwise(days):
            periods |= Q(
                service_period_from=starts_on,
                service_period_until=next_starts_on - dt.timedelta(days=1),
            )

        invoices = Invoice.objects.filter(
            Q(
                title=recurring.title,
                service_period_from__gte=recurring.starts_on,
            )
            | periods
            | Q(title=recurring.title, subtotal=recurring.subtotal),
            recurring_invoice__isnull=True,
            customer_id=recurring.customer_id,
            service_period_from__lt=recurring.next_period_starts_on,
        )
        if recurring.ends_on:
            invoices = invoices.filter(service_period_from__lte=recurring.ends_on)
        for invoice in invoices:
            candidates[invoice][recurring] = (
                invoice.title == recurring.title,
                invoice.subtotal == recurring.subtotal,
                invoice.service_period_from >= recurring.starts_on,
            )

    for invoice, recurrings in candidates.items():
        best = max(recurrings.values())
        matches = [r for r, score in recurrings.items() if score == best]
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
