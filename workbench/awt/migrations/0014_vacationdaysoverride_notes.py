# Generated by Django 3.2.6 on 2021-08-18 09:15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("awt", "0013_vacationdaysoverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="vacationdaysoverride",
            name="notes",
            field=models.CharField(max_length=500, verbose_name="notes"),
        ),
    ]
