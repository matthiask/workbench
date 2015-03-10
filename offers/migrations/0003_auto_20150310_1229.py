# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0009_auto_20150306_1114'),
        ('offers', '0002_auto_20150309_1534'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='offer',
            name='contact',
        ),
        migrations.RemoveField(
            model_name='offer',
            name='customer',
        ),
        migrations.AddField(
            model_name='offer',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, default=4572, to='projects.Project', related_name='offers', verbose_name='project'),
            preserve_default=False,
        ),
    ]
