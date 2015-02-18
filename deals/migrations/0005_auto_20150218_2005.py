# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0004_auto_20150204_1604'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deal',
            name='owned_by',
            field=models.ForeignKey(related_name='+', verbose_name='owned by', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
