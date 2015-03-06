# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0003_auto_20150306_1237'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='loggedaction',
            options={'managed': False, 'ordering': ('created_at',)},
        ),
    ]
