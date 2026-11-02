from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("notes", "0002_fts"),
        ("audit", "0007_statement_timestamp"),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('notes_note', ARRAY['fts_document']);",
            "",
        ),
    ]
