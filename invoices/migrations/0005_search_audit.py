# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from tools.search import migration_sql


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0004_auto_20150315_2140'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('invoices_invoice')",
            ''),
        migrations.RunSQL(*migration_sql(
            'invoices_invoice', 'title, description, postal_address')),
    ]
