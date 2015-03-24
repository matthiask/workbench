# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import datetime
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0001_initial'),
        ('offers', '0001_initial'),
        ('services', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RenderedService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created_at', models.DateTimeField(verbose_name='created at', default=django.utils.timezone.now)),
                ('rendered_on', models.DateField(verbose_name='rendered on', default=datetime.date.today)),
                ('hours', models.DecimalField(verbose_name='hours', decimal_places=2, max_digits=5)),
                ('description', models.TextField(verbose_name='description')),
                ('archived_at', models.DateTimeField(verbose_name='archived at', null=True, blank=True)),
                ('created_by', models.ForeignKey(verbose_name='created by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
                ('invoice', models.ForeignKey(verbose_name='invoice', on_delete=django.db.models.deletion.PROTECT, null=True, to='invoices.Invoice', blank=True, related_name='+')),
                ('rendered_by', models.ForeignKey(verbose_name='rendered by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='renderedservices')),
            ],
            options={
                'verbose_name': 'rendered service',
                'ordering': ('-rendered_on', '-created_at'),
                'verbose_name_plural': 'rendered services',
            },
        ),
        migrations.CreateModel(
            name='RequiredService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('estimated_effort', models.DecimalField(verbose_name='estimated effort', help_text='The original estimate.', decimal_places=2, max_digits=5)),
                ('offered_effort', models.DecimalField(verbose_name='offered effort', help_text='Effort offered to the customer.', decimal_places=2, max_digits=5)),
                ('planning_effort', models.DecimalField(verbose_name='planning effort', help_text='Effort for planning. This value should reflect the current  state of affairs also when work is already in progress.', decimal_places=2, max_digits=5)),
                ('service_type', models.ForeignKey(verbose_name='service type', on_delete=django.db.models.deletion.PROTECT, to='services.ServiceType', related_name='+')),
            ],
            options={
                'verbose_name': 'required service',
                'ordering': ('service_type',),
                'verbose_name_plural': 'required services',
            },
        ),
        migrations.CreateModel(
            name='Story',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created_at', models.DateTimeField(verbose_name='created at', default=django.utils.timezone.now)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('status', models.PositiveIntegerField(verbose_name='status', default=10, choices=[(10, 'unscheduled'), (20, 'scheduled'), (30, 'started'), (40, 'finished'), (50, 'delivered'), (60, 'accepted'), (15, 'rejected')])),
                ('accepted_at', models.DateTimeField(verbose_name='accepted at', null=True, blank=True)),
                ('due_on', models.DateField(verbose_name='due on', null=True, blank=True, help_text='This field should be left empty most of the time.')),
                ('position', models.PositiveIntegerField(verbose_name='position', default=0)),
                ('offer', models.ForeignKey(verbose_name='offer', on_delete=django.db.models.deletion.PROTECT, null=True, to='offers.Offer', blank=True, related_name='stories')),
                ('owned_by', models.ForeignKey(verbose_name='owned by', on_delete=django.db.models.deletion.PROTECT, null=True, to=settings.AUTH_USER_MODEL, blank=True, related_name='+')),
                ('project', models.ForeignKey(verbose_name='project', on_delete=django.db.models.deletion.PROTECT, to='projects.Project', related_name='stories')),
                ('release', models.ForeignKey(verbose_name='release', on_delete=django.db.models.deletion.SET_NULL, null=True, to='projects.Release', blank=True, related_name='stories')),
                ('requested_by', models.ForeignKey(verbose_name='requested by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'verbose_name': 'story',
                'ordering': ('release', 'position', 'id'),
                'verbose_name_plural': 'stories',
            },
        ),
        migrations.AddField(
            model_name='requiredservice',
            name='story',
            field=models.ForeignKey(verbose_name='story', to='stories.Story', related_name='requiredservices'),
        ),
        migrations.AddField(
            model_name='renderedservice',
            name='story',
            field=models.ForeignKey(verbose_name='story', on_delete=django.db.models.deletion.PROTECT, to='stories.Story', related_name='renderedservices'),
        ),
        migrations.AlterUniqueTogether(
            name='requiredservice',
            unique_together=set([('story', 'service_type')]),
        ),
    ]
