# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0004_auto_20150306_1623'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='loggedaction',
            options={'verbose_name_plural': 'logged actions', 'ordering': ('created_at',), 'verbose_name': 'logged action', 'managed': False},
        ),
    ]
