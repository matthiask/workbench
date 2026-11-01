from django.db import migrations

from workbench.tools import search


# Absences aren't searchable anymore: the index contained the descriptions
# of sickness absences, which may be health data.
class Migration(migrations.Migration):
    dependencies = [
        ("awt", "0021_confirm_paid_absences_of_past_years"),
    ]

    operations = [
        migrations.RunSQL(
            """\
DROP TRIGGER IF EXISTS awt_absence_fts_trigger ON awt_absence;
DROP FUNCTION IF EXISTS awt_absence_fts();
DROP INDEX IF EXISTS awt_absence_fts_index;
ALTER TABLE awt_absence DROP COLUMN IF EXISTS fts_document;
""",
            search.create_structure("awt_absence")
            + search.fts("awt_absence", ["description"]),
        ),
    ]
