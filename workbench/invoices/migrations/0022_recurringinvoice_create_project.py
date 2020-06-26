# Generated by Django 3.2 on 2020-06-04 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0021_auto_20200324_0829"),
    ]

    operations = [
        migrations.AddField(
            model_name="recurringinvoice",
            name="create_project",
            field=models.BooleanField(
                default=False,
                help_text="Invoices are created without projects by default.",
                verbose_name="Create project?",
            ),
        ),
    ]