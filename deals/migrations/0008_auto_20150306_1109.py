# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0007_auto_20150302_2300'),
        ('ftool', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('deals_deal');"
            "SELECT audit_audit_table('deals_funnel');",
            '',
        ),
    ]
