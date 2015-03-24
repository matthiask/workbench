# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
        ('deals', '0001_initial'),
        ('projects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('due_on', models.DateField(verbose_name='due on', null=True, blank=True)),
                ('time', models.TimeField(verbose_name='time', null=True, blank=True)),
                ('duration', models.DecimalField(verbose_name='duration', null=True, max_digits=5, blank=True, decimal_places=2, help_text='Duration in hours (if applicable).')),
                ('created_at', models.DateTimeField(verbose_name='created at', default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(verbose_name='completed at', null=True, blank=True)),
                ('contact', models.ForeignKey(verbose_name='contact', on_delete=django.db.models.deletion.PROTECT, null=True, to='contacts.Person', blank=True, related_name='activities')),
                ('deal', models.ForeignKey(verbose_name='deal', on_delete=django.db.models.deletion.PROTECT, null=True, to='deals.Deal', blank=True, related_name='activities')),
                ('owned_by', models.ForeignKey(verbose_name='owned by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='activities')),
                ('project', models.ForeignKey(verbose_name='project', on_delete=django.db.models.deletion.PROTECT, null=True, to='projects.Project', blank=True, related_name='activities')),
            ],
            options={
                'verbose_name': 'activity',
                'ordering': ('due_on',),
                'verbose_name_plural': 'activities',
            },
        ),
    ]
