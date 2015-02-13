# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_auto_20150213_1406'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ProjectManager',
        ),
    ]
