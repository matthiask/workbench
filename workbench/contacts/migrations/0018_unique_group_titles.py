import secrets

from django.db import migrations
from django.db.models.functions import Lower


def rename_duplicates(apps, schema_editor):
    """Group titles become unique (case-insensitive, archived groups too):
    the oldest group keeps its title, the others get a random suffix"""
    Group = apps.get_model("contacts", "Group")
    seen = set()
    for group in Group.objects.annotate(lower=Lower("title")).order_by("pk"):
        if group.lower not in seen:
            seen.add(group.lower)
            continue
        while True:
            suffix = f" ({secrets.token_hex(3)})"
            title = group.title[: 100 - len(suffix)] + suffix
            if title.lower() not in seen:
                break
        seen.add(title.lower())
        Group.objects.filter(pk=group.pk).update(title=title)


class Migration(migrations.Migration):
    dependencies = [("contacts", "0017_industries_apply_to_organizations")]

    operations = [migrations.RunPython(rename_duplicates, migrations.RunPython.noop)]
