# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-24 07:20
from __future__ import unicode_literals

import io, os

from django.conf import settings
import django.contrib.postgres.fields.hstore
from django.contrib.postgres.operations import HStoreExtension, UnaccentExtension
from django.db import migrations, models


with io.open(os.path.join(settings.BASE_DIR, "stuff", "audit.sql")) as f:
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
                "ordering": ("created_at",),
                "verbose_name": "logged action",
                "managed": False,
                "db_table": "audit_logged_actions",
            },
        ),
        migrations.RunSQL(AUDIT_SQL),
    ]
