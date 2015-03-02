# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.conf import settings
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stories', '0007_auto_20150301_1727'),
    ]

    operations = [
        migrations.CreateModel(
            name='RenderedService',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='created at')),
                ('rendered_on', models.DateField(default=datetime.date.today, verbose_name='rendered on')),
                ('hours', models.DecimalField(decimal_places=2, verbose_name='hours', max_digits=5)),
                ('description', models.TextField(verbose_name='description')),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', verbose_name='created by')),
                ('rendered_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='renderedservices', verbose_name='rendered by')),
                ('story', models.ForeignKey(to='stories.Story', related_name='renderedservices', verbose_name='story')),
            ],
            options={
                'verbose_name': 'rendered service',
                'verbose_name_plural': 'rendered services',
                'ordering': ('-rendered_on', '-created_at'),
            },
        ),
    ]
