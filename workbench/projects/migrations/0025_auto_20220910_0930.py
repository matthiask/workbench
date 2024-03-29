# Generated by Django 3.2.14 on 2022-09-10 07:30

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0024_alter_internaltype_percentage"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="internaltype",
            name="is_selectable",
        ),
        migrations.CreateModel(
            name="InternalTypeUser",
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
                    "_percentage",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Inherit the default internal type percentage if left empty.",
                        max_digits=5,
                        null=True,
                        verbose_name="percentage",
                    ),
                ),
                (
                    "internal_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="projects.internaltype",
                        verbose_name="internal type",
                    ),
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
                "verbose_name": "internal type user",
                "verbose_name_plural": "internal type users",
            },
        ),
        migrations.RunSQL(
            "SELECT audit_audit_table('projects_internaltypeuser');",
            "",
        ),
        migrations.RunSQL(
            """
INSERT INTO projects_internaltypeuser (internal_type_id, user_id)
SELECT internaltype_id, user_id
FROM projects_internaltype_assigned_users
            """,
            "",
        ),
    ]
