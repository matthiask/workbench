# Generated by Django 1.10 on 2016-08-24 07:20

import os

import django.contrib.postgres.fields.hstore
from django.conf import settings
from django.contrib.postgres.operations import HStoreExtension, UnaccentExtension
from django.db import migrations, models


with open(
    os.path.join(settings.BASE_DIR, "workbench", "tools", "audit.sql"), encoding="utf-8"
) as f:
    AUDIT_SQL = f.read()


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        HStoreExtension(),
        UnaccentExtension(),
        migrations.CreateModel(
            name="LoggedAction",
            fields=[
                ("event_id", models.IntegerField(primary_key=True, serialize=False)),
                ("table_name", models.TextField()),
                ("user_name", models.TextField(null=True)),
                ("created_at", models.DateTimeField()),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("I", "INSERT"),
                            ("U", "UPDATE"),
                            ("D", "DELETE"),
                            ("T", "TRUNCATE"),
                        ],
                        max_length=1,
                    ),
                ),
                (
                    "row_data",
                    django.contrib.postgres.fields.hstore.HStoreField(null=True),
                ),
                (
                    "changed_fields",
                    django.contrib.postgres.fields.hstore.HStoreField(null=True),
                ),
            ],
            options={
                "verbose_name_plural": "logged actions",
                "ordering": ["event_id"],
                "verbose_name": "logged action",
                "managed": False,
                "db_table": "audit_logged_actions",
            },
        ),
        migrations.RunSQL(AUDIT_SQL),
    ]
