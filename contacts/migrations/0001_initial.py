# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailAddress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('type', models.CharField(verbose_name='type', max_length=40)),
                ('weight', models.SmallIntegerField(verbose_name='weight', editable=False, default=0)),
                ('email', models.EmailField(verbose_name='email', max_length=254)),
            ],
            options={
                'verbose_name': 'email address',
                'ordering': ('-weight', 'id'),
                'verbose_name_plural': 'email addresses',
            },
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('title', models.CharField(verbose_name='title', max_length=100)),
            ],
            options={
                'verbose_name': 'group',
                'ordering': ('title',),
                'verbose_name_plural': 'groups',
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('name', models.TextField(verbose_name='name')),
                ('notes', models.TextField(verbose_name='notes', blank=True)),
                ('groups', models.ManyToManyField(verbose_name='groups', to='contacts.Group', related_name='+')),
                ('primary_contact', models.ForeignKey(verbose_name='primary contact', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'verbose_name': 'organization',
                'ordering': ('name',),
                'verbose_name_plural': 'organizations',
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('full_name', models.CharField(verbose_name='full name', max_length=100)),
                ('address', models.CharField(verbose_name='address', max_length=100, blank=True, help_text='E.g. Dear John.')),
                ('notes', models.TextField(verbose_name='notes', blank=True)),
                ('groups', models.ManyToManyField(verbose_name='groups', to='contacts.Group', related_name='+')),
                ('organization', models.ForeignKey(verbose_name='organization', on_delete=django.db.models.deletion.PROTECT, null=True, to='contacts.Organization', blank=True, related_name='people')),
                ('primary_contact', models.ForeignKey(verbose_name='primary contact', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'verbose_name': 'person',
                'ordering': ('full_name',),
                'verbose_name_plural': 'people',
            },
        ),
        migrations.CreateModel(
            name='PhoneNumber',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('type', models.CharField(verbose_name='type', max_length=40)),
                ('weight', models.SmallIntegerField(verbose_name='weight', editable=False, default=0)),
                ('phone_number', models.CharField(verbose_name='phone number', max_length=100)),
                ('person', models.ForeignKey(verbose_name='person', to='contacts.Person', related_name='phonenumbers')),
            ],
            options={
                'verbose_name': 'phone number',
                'ordering': ('-weight', 'id'),
                'verbose_name_plural': 'phone numbers',
            },
        ),
        migrations.CreateModel(
            name='PostalAddress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('type', models.CharField(verbose_name='type', max_length=40)),
                ('weight', models.SmallIntegerField(verbose_name='weight', editable=False, default=0)),
                ('postal_address', models.TextField(verbose_name='postal address')),
                ('person', models.ForeignKey(verbose_name='person', to='contacts.Person', related_name='postaladdresses')),
            ],
            options={
                'verbose_name': 'postal address',
                'ordering': ('-weight', 'id'),
                'verbose_name_plural': 'postal addresses',
            },
        ),
        migrations.AddField(
            model_name='emailaddress',
            name='person',
            field=models.ForeignKey(verbose_name='person', to='contacts.Person', related_name='emailaddresses'),
        ),
    ]
