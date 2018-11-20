# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-24 20:01
from __future__ import unicode_literals

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("offers", "0008_auto_20160924_1422")]

    operations = [
        migrations.AlterField(
            model_name="cost",
            name="cost",
            field=models.DecimalField(
                decimal_places=2, default=None, max_digits=10, verbose_name="cost"
            ),
        ),
        migrations.AlterField(
            model_name="service",
            name="cost",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=10,
                verbose_name="cost",
            ),
        ),
    ]
