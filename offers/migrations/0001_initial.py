# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('subtotal', models.DecimalField(verbose_name='subtotal', default=0, decimal_places=2, max_digits=10)),
                ('discount', models.DecimalField(verbose_name='discount', default=0, decimal_places=2, max_digits=10)),
                ('tax_rate', models.DecimalField(verbose_name='tax rate', default=8, decimal_places=2, max_digits=10)),
                ('total', models.DecimalField(verbose_name='total', default=0, decimal_places=2, max_digits=10)),
                ('offered_on', models.DateField(verbose_name='offered on', null=True, blank=True)),
                ('closed_at', models.DateTimeField(verbose_name='closed at', null=True, blank=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('status', models.PositiveIntegerField(verbose_name='status', default=10, choices=[(10, 'In preparation'), (20, 'Offered'), (30, 'Accepted'), (40, 'Rejected'), (50, 'Replaced')])),
                ('postal_address', models.TextField(verbose_name='postal address', blank=True)),
                ('story_data', django_pgjson.fields.JsonBField(verbose_name='stories', null=True, blank=True)),
                ('owned_by', models.ForeignKey(verbose_name='owned by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
                ('project', models.ForeignKey(verbose_name='project', on_delete=django.db.models.deletion.PROTECT, to='projects.Project', related_name='offers')),
            ],
            options={
                'verbose_name': 'offer',
                'ordering': ('-id',),
                'verbose_name_plural': 'offers',
            },
        ),
    ]
