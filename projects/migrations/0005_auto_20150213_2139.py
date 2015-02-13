# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0003_auto_20150213_1751'),
        ('projects', '0004_delete_projectmanager'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='contact',
            field=models.ForeignKey(null=True, related_name='+', blank=True, verbose_name='contact', on_delete=django.db.models.deletion.SET_NULL, to='contacts.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='customer',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, verbose_name='customer', related_name='+', to='contacts.Organization'),
            preserve_default=False,
        ),
    ]
