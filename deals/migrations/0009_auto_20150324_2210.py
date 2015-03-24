# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0008_auto_20150306_1109'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='deal',
            name='funnel',
        ),
        migrations.DeleteModel(
            name='Funnel',
        ),
    ]
