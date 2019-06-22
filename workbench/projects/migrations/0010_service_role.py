# Generated by Django 2.2.2 on 2019-06-22 12:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("circles", "0001_initial"),
        ("projects", "0009_service_is_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="role",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="services",
                to="circles.Role",
                verbose_name="role",
            ),
        )
    ]
