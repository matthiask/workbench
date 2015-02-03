# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0002_auto_20150203_1306'),
        ('deals', '0002_deal_funnel'),
    ]

    operations = [
        migrations.CreateModel(
            name='RequiredService',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('hours', models.DecimalField(max_digits=5, decimal_places=2, verbose_name='hours')),
                ('deal', models.ForeignKey(to='deals.Deal', related_name='required_services', verbose_name='deal')),
                ('service_type', models.ForeignKey(to='services.ServiceType', related_name='+', verbose_name='service type')),
            ],
            options={
                'verbose_name_plural': 'required services',
                'verbose_name': 'required service',
            },
            bases=(models.Model,),
        ),
    ]
