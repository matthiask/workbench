# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.postgres.fields.hstore


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoggedAction',
            fields=[
                ('event_id', models.IntegerField(serialize=False, primary_key=True)),
                ('schema_name', models.TextField()),
                ('table_name', models.TextField()),
                ('relid', models.IntegerField()),
                ('session_user_name', models.TextField(null=True)),
                ('action_tstamp_tx', models.DateTimeField()),
                ('action_tstamp_stm', models.DateTimeField()),
                ('transaction_id', models.IntegerField(null=True)),
                ('application_name', models.TextField(null=True)),
                ('client_addr', models.GenericIPAddressField(null=True)),
                ('client_port', models.IntegerField(null=True)),
                ('client_query', models.TextField(null=True)),
                ('action', models.TextField()),
                ('row_data', django.contrib.postgres.fields.hstore.HStoreField(null=True)),
                ('changed_fields', django.contrib.postgres.fields.hstore.HStoreField(null=True)),
                ('statement_only', models.BooleanField()),
            ],
            options={
                'managed': False,
                'db_table': 'audit_logged_actions',
            },
        ),
    ]
