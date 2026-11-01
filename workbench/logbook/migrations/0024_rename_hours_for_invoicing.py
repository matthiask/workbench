from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("logbook", "0023_hours_for_invoicing"),
    ]

    operations = [
        migrations.RenameField(
            model_name="loggedhours",
            old_name="invoiced_hours",
            new_name="hours_for_invoicing",
        ),
    ]
