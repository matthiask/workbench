# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='description',
            field=models.TextField(verbose_name='description', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='status',
            field=models.PositiveIntegerField(verbose_name='status', choices=[(10, 'initial'), (20, 'proposed'), (50, 'started'), (60, 'finished'), (100, 'rejected')], default=10),
            preserve_default=True,
        ),
    ]
