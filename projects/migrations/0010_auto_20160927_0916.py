# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-27 07:16
from __future__ import unicode_literals

from collections import defaultdict
import itertools

from django.db import migrations, models


def forward(apps, schema_editor):
    codes = defaultdict(lambda: itertools.count(start=1))

    Task = apps.get_model("projects", "Task")
    for task in Task.objects.order_by("pk"):
        task._code = next(codes[task.project_id])
        task.save()


class Migration(migrations.Migration):

    dependencies = [("projects", "0009_auto_20160922_1331")]

    operations = [
        migrations.AlterModelOptions(
            name="task",
            options={
                "ordering": ("pk",),
                "verbose_name": "task",
                "verbose_name_plural": "tasks",
            },
        ),
        migrations.AddField(
            model_name="task",
            name="_code",
            field=models.IntegerField(default=0, verbose_name="code"),
            preserve_default=False,
        ),
        migrations.RunPython(forward, lambda apps, schema_editor: None),
    ]
