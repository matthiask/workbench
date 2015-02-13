# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailAddress',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('type', models.CharField(max_length=40, verbose_name='type')),
                ('email', models.EmailField(max_length=254, verbose_name='email')),
            ],
            options={
                'verbose_name_plural': 'email addresses',
                'verbose_name': 'email address',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='title')),
            ],
            options={
                'verbose_name_plural': 'groups',
                'verbose_name': 'group',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.TextField(verbose_name='name')),
                ('primary_contact', models.ForeignKey(related_name='+', verbose_name='primary contact', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('full_name', models.CharField(max_length=100, verbose_name='full name')),
                ('address', models.CharField(max_length=100, verbose_name='address', blank=True, help_text='E.g. Dear John.')),
                ('notes', models.TextField(blank=True, verbose_name='notes')),
                ('organization', models.ForeignKey(related_name='people', verbose_name='organization', to='contacts.Organization')),
                ('primary_contact', models.ForeignKey(related_name='+', verbose_name='primary contact', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'people',
                'verbose_name': 'person',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PhoneNumber',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('type', models.CharField(max_length=40, verbose_name='type')),
                ('phone_number', models.CharField(max_length=100, verbose_name='phone number')),
                ('person', models.ForeignKey(related_name='phonenumbers', verbose_name='person', to='contacts.Person')),
            ],
            options={
                'verbose_name_plural': 'phone numbers',
                'verbose_name': 'phone number',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PostalAddress',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('type', models.CharField(max_length=40, verbose_name='type')),
                ('postal_address', models.TextField(verbose_name='postal address')),
                ('person', models.ForeignKey(related_name='postaladdresses', verbose_name='person', to='contacts.Person')),
            ],
            options={
                'verbose_name_plural': 'postal addresses',
                'verbose_name': 'postal address',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='emailaddress',
            name='person',
            field=models.ForeignKey(related_name='emailaddresses', verbose_name='person', to='contacts.Person'),
            preserve_default=True,
        ),
    ]
