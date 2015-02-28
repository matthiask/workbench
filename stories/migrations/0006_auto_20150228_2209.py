# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stories', '0005_auto_20150225_2025'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='story',
            name='owned_by',
        ),
        migrations.AddField(
            model_name='story',
            name='owned_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, verbose_name='owned by', blank=True, related_name='+', null=True),
        ),
        migrations.AlterField(
            model_name='story',
            name='requested_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, verbose_name='requested by', related_name='+'),
        ),
    ]
