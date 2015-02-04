# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from tools.search import migration_sql


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0003_requiredservice'),
    ]

    operations = [
        migrations.RunSQL(*migration_sql('deals_deal', 'title, description')),
    ]
