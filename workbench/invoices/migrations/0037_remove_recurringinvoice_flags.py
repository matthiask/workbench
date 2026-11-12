from django.db import migrations


class Migration(migrations.Migration):
    """Separate from 0036: altering the table in the same transaction as the
    data migration fails because of the pending audit trigger events"""

    dependencies = [
        ("invoices", "0036_recurring_invoice_new_invoices"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="recurringinvoice",
            name="mark_as_sent",
        ),
        migrations.RemoveField(
            model_name="recurringinvoice",
            name="send_automatically",
        ),
    ]
