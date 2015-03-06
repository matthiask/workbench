# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0003_auto_20150302_2300'),
        ('ftool', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('activities_activity');"
            '',
        ),
    ]
