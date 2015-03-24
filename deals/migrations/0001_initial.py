# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Deal',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('estimated_value', models.DecimalField(verbose_name='estimated value', decimal_places=2, max_digits=10)),
                ('status', models.PositiveIntegerField(verbose_name='status', default=10, choices=[(10, 'initial'), (20, 'negotiating'), (30, 'improbable'), (40, 'probable in the future'), (40, 'probable soon'), (60, 'accepted'), (70, 'declined')])),
                ('created_at', models.DateTimeField(verbose_name='created at', default=django.utils.timezone.now)),
                ('closed_at', models.DateTimeField(verbose_name='closed at', null=True, blank=True)),
                ('owned_by', models.ForeignKey(verbose_name='owned by', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'verbose_name': 'deal',
                'verbose_name_plural': 'deals',
            },
        ),
    ]
