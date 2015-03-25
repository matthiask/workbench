# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='created at'),
        ),
        migrations.AddField(
            model_name='project',
            name='invoicing',
            field=models.BooleanField(default=True, verbose_name='invoicing'),
        ),
        migrations.AddField(
            model_name='project',
            name='maintenance',
            field=models.BooleanField(default=False, verbose_name='maintenance'),
        ),
    ]
