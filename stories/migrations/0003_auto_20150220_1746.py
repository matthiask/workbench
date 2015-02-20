# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0002_auto_20150203_1306'),
        ('stories', '0002_auto_20150202_2211'),
    ]

    operations = [
        migrations.CreateModel(
            name='RequiredService',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('effort_best_case', models.DecimalField(decimal_places=2, verbose_name='best case effort', help_text='Time required if everything falls into place.', max_digits=5)),
                ('effort_safe_case', models.DecimalField(decimal_places=2, verbose_name='safe case effort', help_text='Time required to be almost certain that the work will be completed.', max_digits=5)),
                ('service_type', models.ForeignKey(verbose_name='service type', to='services.ServiceType', related_name='+')),
                ('story', models.ForeignKey(verbose_name='story', to='stories.Story', related_name='requiredservices')),
            ],
            options={
                'verbose_name': 'required service',
                'ordering': ('service_type',),
                'verbose_name_plural': 'required services',
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='requiredservice',
            unique_together=set([('story', 'service_type')]),
        ),
        migrations.RemoveField(
            model_name='story',
            name='effort_best_case',
        ),
        migrations.RemoveField(
            model_name='story',
            name='effort_safe_case',
        ),
    ]
