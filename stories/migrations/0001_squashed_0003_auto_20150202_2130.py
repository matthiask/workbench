# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Story',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
                ('created_at', models.DateTimeField(verbose_name='created at', default=django.utils.timezone.now)),
                ('title', models.CharField(max_length=200, verbose_name='title')),
                ('status', models.PositiveIntegerField(verbose_name='status', default=10, choices=[(10, 'unscheduled'), (20, 'scheduled'), (30, 'started'), (40, 'finished'), (50, 'delivered'), (60, 'accepted'), (15, 'rejected')])),
                ('accepted_at', models.DateTimeField(blank=True, verbose_name='accepted at', null=True)),
                ('effort_best_case', models.DecimalField(blank=True, max_digits=5, verbose_name='best case effort', help_text='Time required if everything falls into place.', null=True, decimal_places=2)),
                ('effort_safe_case', models.DecimalField(blank=True, max_digits=5, verbose_name='safe case effort', help_text='This story can be delivered in this time frame with almost certainty (90%).', null=True, decimal_places=2)),
                ('due_on', models.DateField(blank=True, verbose_name='due on', help_text='This field should be left empty most of the time.', null=True)),
                ('position', models.PositiveIntegerField(verbose_name='position', default=0)),
                ('requested_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, verbose_name='requested by')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('owned_by', models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL, verbose_name='owned by', related_name='owned_stories')),
            ],
            options={
                'ordering': ('position',),
                'verbose_name': 'story',
                'verbose_name_plural': 'stories',
            },
            bases=(models.Model,),
        ),
    ]
