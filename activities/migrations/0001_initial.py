# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0009_auto_20150220_1151'),
        ('deals', '0006_auto_20150220_1734'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('title', models.CharField(max_length=200, verbose_name='title')),
                ('due_on', models.DateField(null=True, verbose_name='due on', blank=True)),
                ('time', models.TimeField(null=True, verbose_name='time', blank=True)),
                ('duration', models.DecimalField(null=True, decimal_places=2, max_digits=5, help_text='Duration in hours (if applicable).', verbose_name='duration', blank=True)),
                ('completed_at', models.DateTimeField(null=True, verbose_name='completed at', blank=True)),
                ('contact', models.ForeignKey(to='contacts.Person', related_name='activities', verbose_name='contact')),
                ('deal', models.ForeignKey(null=True, related_name='activities', to='deals.Deal', verbose_name='deal', blank=True)),
                ('owned_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='activities', verbose_name='owned by')),
            ],
            options={
                'verbose_name_plural': 'activities',
                'verbose_name': 'activity',
            },
            bases=(models.Model,),
        ),
    ]
