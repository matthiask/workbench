# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0008_auto_20150302_2300'),
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('projects_project');"
            "SELECT audit_audit_table('projects_release');",
            '',
        ),
    ]
