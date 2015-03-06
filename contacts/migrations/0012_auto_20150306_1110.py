# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0011_auto_20150302_2300'),
        ('ftool', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "SELECT audit_audit_table('contacts_organization');"
            "SELECT audit_audit_table('contacts_person');"
            "SELECT audit_audit_table('contacts_phonenumber');"
            "SELECT audit_audit_table('contacts_emailaddress');"
            "SELECT audit_audit_table('contacts_postaladdress');",
            '',
        ),
    ]
