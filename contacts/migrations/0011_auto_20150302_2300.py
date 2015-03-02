# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0010_auto_20150223_0908'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='primary_contact',
            field=models.ForeignKey(verbose_name='primary contact', related_name='+', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='person',
            name='organization',
            field=models.ForeignKey(verbose_name='organization', related_name='people', on_delete=django.db.models.deletion.PROTECT, null=True, to='contacts.Organization', blank=True),
        ),
        migrations.AlterField(
            model_name='person',
            name='primary_contact',
            field=models.ForeignKey(verbose_name='primary contact', related_name='+', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]
