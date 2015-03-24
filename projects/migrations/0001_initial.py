# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contacts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('status', models.PositiveIntegerField(verbose_name='status', default=10, choices=[(10, 'In preparation'), (20, 'Work in progress'), (30, 'Finished')])),
                ('contact', models.ForeignKey(verbose_name='contact', on_delete=django.db.models.deletion.SET_NULL, null=True, to='contacts.Person', blank=True, related_name='+')),
                ('customer', models.ForeignKey(verbose_name='customer', on_delete=django.db.models.deletion.PROTECT, to='contacts.Organization', related_name='+')),
                ('owned_by', models.ForeignKey(verbose_name='owned by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'verbose_name': 'project',
                'ordering': ('-id',),
                'verbose_name_plural': 'projects',
            },
        ),
        migrations.CreateModel(
            name='Release',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('is_default', models.BooleanField(verbose_name='is default', default=False)),
                ('position', models.PositiveIntegerField(verbose_name='position', default=0)),
                ('project', models.ForeignKey(verbose_name='project', to='projects.Project', related_name='releases')),
            ],
            options={
                'verbose_name': 'release',
                'ordering': ('position', 'id'),
                'verbose_name_plural': 'releases',
            },
        ),
    ]
