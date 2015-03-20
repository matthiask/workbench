# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0009_auto_20150306_1114'),
        ('activities', '0004_auto_20150306_1114'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='project',
            field=models.ForeignKey(blank=True, to='projects.Project', on_delete=django.db.models.deletion.PROTECT, null=True, verbose_name='project', related_name='activities'),
        ),
        migrations.AlterField(
            model_name='activity',
            name='contact',
            field=models.ForeignKey(blank=True, to='contacts.Person', on_delete=django.db.models.deletion.PROTECT, null=True, verbose_name='contact', related_name='activities'),
        ),
        migrations.AlterField(
            model_name='activity',
            name='deal',
            field=models.ForeignKey(blank=True, to='deals.Deal', on_delete=django.db.models.deletion.PROTECT, null=True, verbose_name='deal', related_name='activities'),
        ),
    ]
