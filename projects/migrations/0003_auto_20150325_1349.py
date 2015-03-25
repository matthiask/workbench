# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_auto_20150325_1325'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='invoicing',
            field=models.BooleanField(verbose_name='invoicing', help_text='This project is eligible for invoicing.', default=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='maintenance',
            field=models.BooleanField(verbose_name='maintenance', help_text='This project is used for maintenance work.', default=False),
        ),
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.PositiveIntegerField(verbose_name='status', default=10, choices=[(10, 'Acquisition'), (20, 'Work in progress'), (30, 'Finished')]),
        ),
    ]
