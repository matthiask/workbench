# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0005_auto_20150218_2005'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='requiredservice',
            name='deal',
        ),
        migrations.RemoveField(
            model_name='requiredservice',
            name='service_type',
        ),
        migrations.DeleteModel(
            name='RequiredService',
        ),
    ]
