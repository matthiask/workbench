# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from tools.search import migration_sql


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_auto_20150203_1304'),
    ]

    operations = [
        migrations.RunSQL(*migration_sql(
            'projects_project',
            'title, description',
        )),
    ]
