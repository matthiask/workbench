from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0005_auto_20210206_1042"),
        ("awt", "0004_auto_20190327_0945"),
    ]

    operations = [
        migrations.RunSQL(
            "UPDATE audit_logged_actions SET row_data=delete(row_data, 'fts_document')"
            " WHERE table_name='awt_absence';"
            "UPDATE audit_logged_actions SET changed_fields=delete(changed_fields, 'fts_document')"
            " WHERE table_name='awt_absence';"
            "SELECT audit_audit_table('awt_absence', ARRAY['fts_document']);",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
