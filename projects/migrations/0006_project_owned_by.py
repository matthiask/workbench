# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0005_auto_20150213_2139'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='owned_by',
            field=models.ForeignKey(default=1, verbose_name='owned by', related_name='+', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
