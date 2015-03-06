# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0009_auto_20150302_2300'),
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('stories_story');"
            "SELECT audit_audit_table('stories_requiredservice');"
            "SELECT audit_audit_table('stories_renderedservice');",
            '',
        ),
    ]
