# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0001_initial'),
        ('stories', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='stories',
            field=models.ManyToManyField(verbose_name='stories', to='stories.Story', blank=True, related_name='invoices'),
        ),
    ]
