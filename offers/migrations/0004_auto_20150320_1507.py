# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0003_auto_20150310_1229'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offer',
            name='story_data',
            field=django_pgjson.fields.JsonBField(null=True, verbose_name='stories', blank=True),
        ),
    ]
