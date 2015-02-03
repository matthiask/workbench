# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='servicetype',
            options={'verbose_name_plural': 'service types', 'verbose_name': 'service type', 'ordering': ('position', 'id')},
        ),
    ]
