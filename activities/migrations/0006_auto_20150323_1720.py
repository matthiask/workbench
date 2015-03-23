# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0005_auto_20150320_0936'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='activity',
            options={'ordering': ('due_on',), 'verbose_name': 'activity', 'verbose_name_plural': 'activities'},
        ),
    ]
