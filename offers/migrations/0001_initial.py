# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import django_pgjson.fields
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0010_auto_20150306_1114'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contacts', '0012_auto_20150306_1110'),
    ]

    operations = [
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('offered_on', models.DateField(null=True, blank=True, verbose_name='offered on')),
                ('closed_at', models.DateTimeField(null=True, blank=True, verbose_name='closed at')),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('status', models.PositiveIntegerField(choices=[(10, 'In preparation'), (20, 'Offered'), (30, 'Accepted'), (40, 'Rejected'), (50, 'Replaced')], verbose_name='status', default=10)),
                ('postal_address', models.TextField(blank=True, verbose_name='postal address')),
                ('story_data', django_pgjson.fields.JsonBField(verbose_name='stories')),
                ('subtotal', models.DecimalField(verbose_name='subtotal', max_digits=10, decimal_places=2, default=0)),
                ('discount', models.DecimalField(verbose_name='discount', max_digits=10, decimal_places=2, default=0)),
                ('tax_rate', models.DecimalField(verbose_name='tax rate', max_digits=10, decimal_places=2, default=0)),
                ('total', models.DecimalField(verbose_name='total', max_digits=10, decimal_places=2, default=0)),
                ('contact', models.ForeignKey(blank=True, to='contacts.Person', related_name='+', null=True, verbose_name='contact', on_delete=django.db.models.deletion.SET_NULL)),
                ('customer', models.ForeignKey(verbose_name='customer', related_name='+', to='contacts.Organization', on_delete=django.db.models.deletion.PROTECT)),
                ('owned_by', models.ForeignKey(verbose_name='owned by', related_name='+', to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
                ('stories', models.ManyToManyField(blank=True, verbose_name='stories', related_name='offers', to='stories.Story')),
            ],
            options={
                'verbose_name_plural': 'offers',
                'verbose_name': 'offer',
                'ordering': ('-id',),
            },
        ),
    ]
