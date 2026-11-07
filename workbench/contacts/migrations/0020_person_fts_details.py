from django.db import migrations

from workbench.tools import search


class Migration(migrations.Migration):
    """projects.0030_search_fix redefined the trigger without ``_fts``, so
    people weren't found by their organization and details anymore"""

    dependencies = [
        ("contacts", "0019_group_unique_title"),
        ("projects", "0030_search_fix"),
    ]

    operations = [
        migrations.RunSQL(
            search.fts(
                "contacts_person",
                ["given_name", "family_name", "address", "notes", "_fts"],
            )
        ),
        migrations.RunSQL("UPDATE contacts_person SET id=id"),
    ]
