# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('password', models.CharField(verbose_name='password', max_length=128)),
                ('last_login', models.DateTimeField(verbose_name='last login', null=True, blank=True)),
                ('email', models.EmailField(verbose_name='email', max_length=254, unique=True)),
                ('is_active', models.BooleanField(verbose_name='is active', default=True)),
                ('is_admin', models.BooleanField(verbose_name='is admin', default=False)),
                ('date_of_birth', models.DateField(verbose_name='date of birth')),
                ('_short_name', models.CharField(verbose_name='short name', max_length=30, blank=True)),
                ('_full_name', models.CharField(verbose_name='full name', max_length=200, blank=True)),
            ],
            options={
                'verbose_name': 'user',
                'ordering': ('_full_name',),
                'verbose_name_plural': 'users',
            },
        ),
    ]
