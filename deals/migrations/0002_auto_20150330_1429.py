# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Stage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('position', models.PositiveIntegerField(verbose_name='position', default=0)),
            ],
            options={
                'verbose_name': 'stage',
                'ordering': ('position', 'id'),
                'verbose_name_plural': 'stages',
            },
        ),
        migrations.AlterField(
            model_name='deal',
            name='status',
            field=models.PositiveIntegerField(verbose_name='status', choices=[(10, 'open'), (20, 'accepted'), (30, 'declined')], default=10),
        ),
        migrations.AddField(
            model_name='deal',
            name='stage',
            field=models.ForeignKey(verbose_name='stage', on_delete=django.db.models.deletion.PROTECT, to='deals.Stage', related_name='deals', default=1),
            preserve_default=False,
        ),
    ]
