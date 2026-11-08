from django.conf import settings
from django.db import migrations
from django.utils.translation import gettext, override

from workbench.tools.formats import currency, local_date_format


def backfill(apps, schema_editor):
    """Paid invoices need a payment notice: the details of their credit entry
    like ``CreditEntry.mark_invoice_as_paid()`` writes them, or the date of
    the payment"""
    Invoice = apps.get_model("invoices", "Invoice")
    CreditEntry = apps.get_model("credit_control", "CreditEntry")

    entries = {
        entry.invoice_id: entry
        for entry in CreditEntry.objects.filter(
            invoice__status=40, invoice__payment_notice=""
        ).select_related("ledger")
    }
    with override(settings.WORKBENCH.PDF_LANGUAGE):
        paid = gettext("Paid")
    for invoice in Invoice.objects.filter(status=40, payment_notice=""):
        if entry := entries.get(invoice.pk):
            notice = "\n".join(
                filter(
                    None,
                    [
                        (
                            f"{local_date_format(entry.value_date)}, {entry.ledger.name},"
                            f" {currency(entry.total)}: {entry.payment_notice}"
                        ),
                        entry.notes,
                    ],
                )
            )
        elif invoice.closed_on:
            notice = f"{paid} {local_date_format(invoice.closed_on)}"
        else:
            notice = paid
        Invoice.objects.filter(pk=invoice.pk).update(payment_notice=notice)


class Migration(migrations.Migration):
    dependencies = [
        ("invoices", "0033_payment_notice_help_text"),
        ("credit_control", "0009_ledger_is_active"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
