# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0006_auto_20150228_2209'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='story',
            options={'ordering': ('release', 'position', 'id'), 'verbose_name': 'story', 'verbose_name_plural': 'stories'},
        ),
    ]
