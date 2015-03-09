# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from tools.search import migration_sql


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('offers_offer')",
            ''),
        migrations.RunSQL(*migration_sql(
            'offers_offer', 'title, description, postal_address')),
    ]
