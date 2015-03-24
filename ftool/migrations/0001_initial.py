# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import io
import os

from django.conf import settings
from django.db import models, migrations


with io.open(os.path.join(settings.BASE_DIR, 'stuff', 'audit.sql')) as f:
    sql = f.read()


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(sql, None),
        migrations.RunSQL(
            "SELECT audit_audit_table('accounts_user');"
            "SELECT audit_audit_table('activities_activity');"
            "SELECT audit_audit_table('contacts_emailaddress');"
            "SELECT audit_audit_table('contacts_organization');"
            "SELECT audit_audit_table('contacts_person');"
            "SELECT audit_audit_table('contacts_phonenumber');"
            "SELECT audit_audit_table('contacts_postaladdress');"
            "SELECT audit_audit_table('deals_deal');"
            "SELECT audit_audit_table('invoices_invoice');"
            "SELECT audit_audit_table('offers_offer');"
            "SELECT audit_audit_table('projects_project');"
            "SELECT audit_audit_table('projects_release');"
            "SELECT audit_audit_table('stories_renderedservice');"
            "SELECT audit_audit_table('stories_requiredservice');"
            "SELECT audit_audit_table('stories_story');",
            ""),
    ]
