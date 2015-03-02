# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_auto_20150219_2250'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='owned_by',
            field=models.ForeignKey(verbose_name='owned by', related_name='+', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]
