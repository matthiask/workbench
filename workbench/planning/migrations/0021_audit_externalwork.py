from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0020_external_work_provided_by_protect"),
    ]

    operations = [
        migrations.RunSQL("SELECT audit_audit_table('planning_externalwork');", "")
    ]
