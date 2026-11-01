from django.db import migrations


def forwards(apps, schema_editor):
    """Industry groups ("Branche - ...") apply to organizations: people with
    an organization are in them through their organization (the same as
    Group.move_people_to_organizations())"""
    Group = apps.get_model("contacts", "Group")
    Organization = apps.get_model("contacts", "Organization")
    Person = apps.get_model("contacts", "Person")

    for group in Group.objects.filter(title__istartswith="Branche"):
        group.applies_to_organizations = True
        group.save(update_fields=["applies_to_organizations"])
        memberships = Person.groups.through.objects.filter(
            group=group, person__organization__isnull=False
        )
        group.organization_set.add(
            *Organization.objects.filter(
                people__in=memberships.values("person")
            ).distinct()
        )
        memberships.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0016_group_applies_to_organizations"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
