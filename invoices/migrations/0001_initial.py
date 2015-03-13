# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0009_auto_20150306_1114'),
        ('contacts', '0012_auto_20150306_1110'),
        ('stories', '0010_auto_20150306_1114'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('status', models.PositiveIntegerField(choices=[(10, 'In preparation'), (20, 'Sent'), (30, 'Reminded'), (40, 'Paid'), (50, 'Canceled'), (60, 'Replaced')], verbose_name='status', default=10)),
                ('type', models.CharField(choices=[('fixed', 'Fixed'), ('services', 'Services'), ('down-payment', 'Down payment')], verbose_name='type', max_length=20)),
                ('postal_address', models.TextField(verbose_name='postal address', blank=True)),
                ('story_data', django_pgjson.fields.JsonBField(verbose_name='stories')),
                ('subtotal', models.DecimalField(verbose_name='subtotal', decimal_places=2, default=0, max_digits=10)),
                ('discount', models.DecimalField(verbose_name='discount', decimal_places=2, default=0, max_digits=10)),
                ('tax_rate', models.DecimalField(verbose_name='tax rate', decimal_places=2, default=0, max_digits=10)),
                ('total', models.DecimalField(verbose_name='total', decimal_places=2, default=0, max_digits=10)),
                ('contact', models.ForeignKey(null=True, related_name='+', verbose_name='contact', to='contacts.Person', blank=True, on_delete=django.db.models.deletion.SET_NULL)),
                ('customer', models.ForeignKey(related_name='+', verbose_name='customer', to='contacts.Organization', on_delete=django.db.models.deletion.PROTECT)),
                ('owned_by', models.ForeignKey(related_name='+', verbose_name='owned by', to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
                ('project', models.ForeignKey(null=True, related_name='+', verbose_name='project', to='projects.Project', blank=True, on_delete=django.db.models.deletion.PROTECT)),
                ('stories', models.ManyToManyField(verbose_name='stories', blank=True, to='stories.Story', related_name='invoices')),
            ],
            options={
                'verbose_name': 'invoice',
                'verbose_name_plural': 'invoices',
                'ordering': ('-id',),
            },
        ),
    ]
