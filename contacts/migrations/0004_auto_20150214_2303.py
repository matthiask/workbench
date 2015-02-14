# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0003_auto_20150213_1751'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='organization',
            options={'verbose_name_plural': 'organizations', 'ordering': ('name',), 'verbose_name': 'organization'},
        ),
        migrations.AlterModelOptions(
            name='person',
            options={'verbose_name_plural': 'people', 'ordering': ('full_name',), 'verbose_name': 'person'},
        ),
    ]
