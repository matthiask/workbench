from django.db import migrations, models


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
        migrations.AlterField(
            model_name="recurringinvoice",
            name="new_invoices",
            field=models.CharField(
                choices=[
                    ("prepare", "Create them in preparation"),
                    (
                        "mark_as_sent",
                        "Create them and mark them as sent (if they are sent another way)",
                    ),
                    ("send", "Send them by email automatically"),
                ],
                default="prepare",
                help_text="New invoices which would be dated on or before the freeze date are dated the day after it.",
                max_length=20,
                verbose_name="new invoices",
            ),
        ),
        migrations.AlterField(
            model_name="recurringinvoice",
            name="send_to",
            field=models.EmailField(
                blank=True,
                help_text="Proposed: the accounts payable address of the organization, the contact or the central address. The owner gets a copy and the replies.",
                max_length=254,
                verbose_name="recipient",
            ),
        ),
    ]
