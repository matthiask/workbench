import os

from django.conf import settings
from django.db import migrations


# Log actions with the time of their statement instead of the start of their
# transaction, which may be a long request or management command
with open(
    os.path.join(settings.BASE_DIR, "workbench", "tools", "audit.sql"), encoding="utf-8"
) as f:
    AUDIT_SQL = f.read()


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0006_absence_fts_document"),
    ]

    operations = [
        migrations.RunSQL(AUDIT_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
