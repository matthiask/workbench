# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-11-21 09:03
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("calendar", "0002_auto_20181121_0922")]

    operations = [
        migrations.AlterField(
            model_name="day",
            name="app",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="days",
                to="calendar.App",
                verbose_name="app",
            ),
        ),
        migrations.AlterField(
            model_name="dayofweekdefault",
            name="day_of_week",
            field=models.IntegerField(
                choices=[
                    (0, "Monday"),
                    (1, "Tuesday"),
                    (2, "Wednesday"),
                    (3, "Thursday"),
                    (4, "Friday"),
                    (5, "Saturday"),
                    (6, "Sunday"),
                ],
                verbose_name="day of week",
            ),
        ),
        migrations.AlterField(
            model_name="presence",
            name="app",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="presences",
                to="calendar.App",
                verbose_name="app",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="dayofweekdefault", unique_together=set([("app", "day_of_week")])
        ),
    ]
