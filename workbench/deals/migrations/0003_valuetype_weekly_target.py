# Generated by Django 3.0.4 on 2020-03-05 10:26

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("deals", "0002_auto_20200219_1234"),
    ]

    operations = [
        migrations.AddField(
            model_name="valuetype",
            name="weekly_target",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="weekly target",
            ),
        ),
    ]
