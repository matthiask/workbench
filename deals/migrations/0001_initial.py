# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Deal',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='title')),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('estimated_value', models.DecimalField(max_digits=10, verbose_name='estimated value', decimal_places=2)),
                ('status', models.PositiveIntegerField(choices=[(10, 'initial'), (20, 'negotiating'), (30, 'improbable'), (40, 'probable in the future'), (40, 'probable soon'), (60, 'accepted'), (70, 'declined')], default=10, verbose_name='status')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='created at')),
                ('closed_at', models.DateTimeField(null=True, verbose_name='closed at', blank=True)),
                ('owned_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, verbose_name='owned by')),
            ],
            options={
                'verbose_name_plural': 'deals',
                'verbose_name': 'deal',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Funnel',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='funnel')),
            ],
            options={
                'verbose_name_plural': 'funnels',
                'verbose_name': 'funnel',
                'ordering': ('title',),
            },
            bases=(models.Model,),
        ),
    ]
