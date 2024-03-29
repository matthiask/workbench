# Generated by Django 3.0.3 on 2020-02-22 10:11

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("timer", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Timestamp",
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
                    "type",
                    models.CharField(
                        choices=[
                            ("start", "Start"),
                            ("split", "Split"),
                            ("stop", "Stop"),
                            ("logbook", "Logbook"),
                            ("break", "Break"),
                        ],
                        max_length=10,
                        verbose_name="type",
                    ),
                ),
                (
                    "notes",
                    models.CharField(blank=True, max_length=500, verbose_name="notes"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "timestamp",
                "verbose_name_plural": "timestamps",
                "ordering": ["-pk"],
            },
        ),
    ]
