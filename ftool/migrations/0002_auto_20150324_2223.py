# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from tools.search import migration_sql


class Migration(migrations.Migration):

    dependencies = [
        ('ftool', '0001_initial'),
        ('activities', '0001_initial'),
        ('contacts', '0001_initial'),
        ('deals', '0001_initial'),
        ('invoices', '0001_initial'),
        ('offers', '0001_initial'),
        ('projects', '0001_initial'),
        ('stories', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(*migration_sql(table, fields))
        for table, fields in [
            (
                'activities_activity',
                'title',
            ),
            (
                'contacts_organization',
                'name, notes',
            ),
            (
                'contacts_person',
                'full_name, address, notes',
            ),
            (
                'deals_deal',
                'title, description',
            ),
            (
                'invoices_invoice',
                'title, description, postal_address',
            ),
            (
                'offers_offer',
                'title, description, postal_address',
            ),
            (
                'projects_project',
                'title, description',
            ),
            (
                'stories_story',
                'title, description',
            ),
            (
                'stories_renderedservice',
                'description',
            ),
        ]
    ]
