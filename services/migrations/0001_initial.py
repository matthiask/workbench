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
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('title', models.CharField(verbose_name='title', max_length=40)),
                ('billing_per_hour', models.DecimalField(verbose_name='billing per hour', max_digits=5, decimal_places=2)),
                ('position', models.PositiveIntegerField(default=0, verbose_name='position')),
            ],
            options={
                'verbose_name': 'service',
                'ordering': ('position', 'id'),
                'verbose_name_plural': 'services',
            },
            bases=(models.Model,),
        ),
    ]
