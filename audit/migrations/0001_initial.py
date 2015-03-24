# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.postgres.fields.hstore


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='LoggedAction',
            fields=[
                ('event_id', models.IntegerField(serialize=False, primary_key=True)),
                ('table_name', models.TextField()),
                ('user_name', models.TextField(null=True)),
                ('created_at', models.DateTimeField()),
                ('action', models.CharField(max_length=1, choices=[('I', 'INSERT'), ('U', 'UPDATE'), ('D', 'DELETE'), ('T', 'TRUNCATE')])),
                ('row_data', django.contrib.postgres.fields.hstore.HStoreField(null=True)),
                ('changed_fields', django.contrib.postgres.fields.hstore.HStoreField(null=True)),
            ],
            options={
                'verbose_name': 'logged action',
                'ordering': ('created_at',),
                'db_table': 'audit_logged_actions',
                'managed': False,
                'verbose_name_plural': 'logged actions',
            },
        ),
    ]
