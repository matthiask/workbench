# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ftool', '0002_loggedaction'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='loggedaction',
            options={'managed': False, 'ordering': ('action_tstamp_stm',)},
        ),
    ]
