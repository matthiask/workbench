# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('title', models.CharField(verbose_name='title', max_length=40)),
                ('billing_per_hour', models.DecimalField(verbose_name='billing per hour', decimal_places=2, max_digits=5)),
                ('position', models.PositiveIntegerField(verbose_name='position', default=0)),
            ],
            options={
                'verbose_name': 'service type',
                'ordering': ('position', 'id'),
                'verbose_name_plural': 'service types',
            },
        ),
    ]
