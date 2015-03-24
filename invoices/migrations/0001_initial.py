# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
        ('projects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('subtotal', models.DecimalField(verbose_name='subtotal', default=0, decimal_places=2, max_digits=10)),
                ('discount', models.DecimalField(verbose_name='discount', default=0, decimal_places=2, max_digits=10)),
                ('tax_rate', models.DecimalField(verbose_name='tax rate', default=8, decimal_places=2, max_digits=10)),
                ('total', models.DecimalField(verbose_name='total', default=0, decimal_places=2, max_digits=10)),
                ('invoiced_on', models.DateField(verbose_name='invoiced on', null=True, blank=True)),
                ('due_on', models.DateField(verbose_name='due on', null=True, blank=True)),
                ('closed_at', models.DateTimeField(verbose_name='closed at', null=True, blank=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('status', models.PositiveIntegerField(verbose_name='status', default=10, choices=[(10, 'In preparation'), (20, 'Sent'), (30, 'Reminded'), (40, 'Paid'), (50, 'Canceled'), (60, 'Replaced')])),
                ('type', models.CharField(verbose_name='type', max_length=20, choices=[('fixed', 'Fixed amount'), ('services', 'Services'), ('down-payment', 'Down payment')])),
                ('postal_address', models.TextField(verbose_name='postal address', blank=True)),
                ('story_data', django_pgjson.fields.JsonBField(verbose_name='stories', null=True, blank=True)),
                ('contact', models.ForeignKey(verbose_name='contact', on_delete=django.db.models.deletion.SET_NULL, null=True, to='contacts.Person', blank=True, related_name='+')),
                ('customer', models.ForeignKey(verbose_name='customer', on_delete=django.db.models.deletion.PROTECT, to='contacts.Organization', related_name='+')),
                ('down_payment_applied_to', models.ForeignKey(verbose_name='down payment applied to', on_delete=django.db.models.deletion.PROTECT, null=True, to='invoices.Invoice', blank=True, related_name='+')),
                ('owned_by', models.ForeignKey(verbose_name='owned by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
                ('project', models.ForeignKey(verbose_name='project', on_delete=django.db.models.deletion.PROTECT, null=True, to='projects.Project', blank=True, related_name='+')),
            ],
            options={
                'verbose_name': 'invoice',
                'ordering': ('-id',),
                'verbose_name_plural': 'invoices',
            },
        ),
    ]
