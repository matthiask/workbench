# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(verbose_name='last login', default=django.utils.timezone.now)),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='email')),
                ('is_active', models.BooleanField(verbose_name='is active', default=True)),
                ('is_admin', models.BooleanField(verbose_name='is admin', default=False)),
                ('date_of_birth', models.DateField(verbose_name='date of birth')),
                ('_short_name', models.CharField(max_length=30, blank=True, verbose_name='short name')),
                ('_full_name', models.CharField(max_length=200, blank=True, verbose_name='full name')),
            ],
            options={
                'ordering': ('_full_name',),
                'verbose_name_plural': 'users',
                'verbose_name': 'user',
            },
            bases=(models.Model,),
        ),
    ]
