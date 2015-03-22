# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0005_auto_20150320_1534'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='offer',
            name='stories',
        ),
    ]
