# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_auto_20150325_1349'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.PositiveIntegerField(verbose_name='status', choices=[(10, 'Acquisition'), (20, 'Work in progress'), (30, 'Finished'), (40, 'Declined')], default=10),
        ),
    ]
