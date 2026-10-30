from django.db import migrations

from workbench.tools import search


class Migration(migrations.Migration):
    dependencies = [
        ("notes", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(search.create_structure("notes_note")),
        migrations.RunSQL(search.fts("notes_note", ["title", "description"])),
        # Index the existing notes
        migrations.RunSQL("UPDATE notes_note SET title=title"),
    ]
