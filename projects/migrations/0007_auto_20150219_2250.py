# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0006_project_owned_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.PositiveIntegerField(choices=[(10, 'In preparation'), (20, 'Work in progress'), (30, 'Finished')], verbose_name='status', default=10),
            preserve_default=True,
        ),
    ]
