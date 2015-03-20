# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0005_search_audit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='story_data',
            field=django_pgjson.fields.JsonBField(null=True, verbose_name='stories', blank=True),
        ),
    ]
