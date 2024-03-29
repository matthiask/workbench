# Generated by Django 3.2.2 on 2021-06-07 11:53

import django.contrib.postgres.fields
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0015_auto_20210204_1440"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoffeePairings",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="created at"
                    ),
                ),
                (
                    "users",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.SmallIntegerField(),
                        size=None,
                        verbose_name="users",
                    ),
                ),
            ],
            options={
                "verbose_name": "coffee pairings",
                "verbose_name_plural": "coffee pairings",
            },
        ),
    ]
