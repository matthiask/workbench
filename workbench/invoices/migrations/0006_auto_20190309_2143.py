# Generated by Django 2.1.7 on 2019-03-09 20:43

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0004_auto_20190309_1004"),
        ("services", "0002_auto_20190304_2247"),
        ("invoices", "0005_auto_20190307_0925"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cost",
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
                ("title", models.CharField(max_length=200, verbose_name="title")),
                (
                    "cost",
                    models.DecimalField(
                        decimal_places=2,
                        default=None,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="cost",
                    ),
                ),
                (
                    "third_party_costs",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        default=None,
                        help_text="Total incl. tax for third-party services.",
                        max_digits=10,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="third party costs",
                    ),
                ),
            ],
            options={
                "verbose_name": "cost",
                "verbose_name_plural": "costs",
                "ordering": ["pk"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Effort",
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
                ("title", models.CharField(max_length=200, verbose_name="title")),
                (
                    "billing_per_hour",
                    models.DecimalField(
                        decimal_places=2,
                        default=None,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="billing per hour",
                    ),
                ),
                (
                    "hours",
                    models.DecimalField(
                        decimal_places=1,
                        max_digits=4,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.1"))
                        ],
                        verbose_name="hours",
                    ),
                ),
            ],
            options={
                "verbose_name": "effort",
                "verbose_name_plural": "efforts",
                "ordering": ["pk"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Service",
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
                ("title", models.CharField(max_length=200, verbose_name="title")),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="description"),
                ),
                (
                    "position",
                    models.PositiveIntegerField(default=0, verbose_name="position"),
                ),
                (
                    "effort_hours",
                    models.DecimalField(
                        decimal_places=1,
                        default=0,
                        max_digits=4,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.1"))
                        ],
                        verbose_name="effort hours",
                    ),
                ),
                (
                    "cost",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="cost",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="services",
                        to="invoices.Invoice",
                        verbose_name="invoice",
                    ),
                ),
                (
                    "project_service",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoice_services",
                        to="projects.Service",
                        verbose_name="project service",
                    ),
                ),
            ],
            options={
                "verbose_name": "service",
                "verbose_name_plural": "services",
                "ordering": ["position", "created_at"],
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="effort",
            name="service",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="efforts",
                to="invoices.Service",
                verbose_name="service",
            ),
        ),
        migrations.AddField(
            model_name="effort",
            name="service_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="services.ServiceType",
                verbose_name="service type",
            ),
        ),
        migrations.AddField(
            model_name="cost",
            name="service",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="costs",
                to="invoices.Service",
                verbose_name="service",
            ),
        ),
    ]
