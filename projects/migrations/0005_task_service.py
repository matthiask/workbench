# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-17 18:55
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("offers", "0002_auto_20160917_2027"),
        ("projects", "0004_auto_20160917_1336"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="service",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tasks",
                to="offers.Service",
                verbose_name="service",
            ),
        )
    ]
