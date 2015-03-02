# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0002_activity_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='contact',
            field=models.ForeignKey(verbose_name='contact', related_name='activities', on_delete=django.db.models.deletion.PROTECT, to='contacts.Person'),
        ),
        migrations.AlterField(
            model_name='activity',
            name='deal',
            field=models.ForeignKey(verbose_name='deal', related_name='activities', on_delete=django.db.models.deletion.SET_NULL, null=True, to='deals.Deal', blank=True),
        ),
        migrations.AlterField(
            model_name='activity',
            name='owned_by',
            field=models.ForeignKey(verbose_name='owned by', related_name='activities', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]
