# Generated by Django 2.2.2 on 2019-07-03 06:01

from django.db import migrations


def forwards(apps, schema_editor):
    Model = apps.get_model("contacts.Person")
    for instance in Model.objects.select_related("organization"):
        instance._fts = " ".join(
            str(part)
            for part in [instance.organization.name if instance.organization else ""]
        )
        instance.save()


class Migration(migrations.Migration):
    dependencies = [("contacts", "0007_person__fts")]

    operations = [migrations.RunPython(forwards, lambda *a: None)]
