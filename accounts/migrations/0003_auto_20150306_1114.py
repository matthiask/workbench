# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_auto_20150228_1035'),
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('accounts_user');"
            '',
        ),
    ]
