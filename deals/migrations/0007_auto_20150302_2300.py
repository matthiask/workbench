# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0006_auto_20150220_1734'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deal',
            name='funnel',
            field=models.ForeignKey(verbose_name='funnel', related_name='deals', on_delete=django.db.models.deletion.PROTECT, to='deals.Funnel'),
        ),
        migrations.AlterField(
            model_name='deal',
            name='owned_by',
            field=models.ForeignKey(verbose_name='owned by', related_name='+', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]
