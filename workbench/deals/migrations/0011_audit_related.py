from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("deals", "0010_deal_related_projects"),
    ]

    operations = [
        migrations.RunSQL("SELECT audit_audit_table('deals_deal_related_offers');", ""),
        migrations.RunSQL(
            "SELECT audit_audit_table('deals_deal_related_projects');", ""
        ),
    ]
