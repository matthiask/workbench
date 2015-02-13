# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from tools.search import migration_sql


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(*migration_sql(
            'contacts_organization',
            'name',
        )),
        migrations.RunSQL(*migration_sql(
            'contacts_person',
            'full_name, address, notes',
        )),
    ]
