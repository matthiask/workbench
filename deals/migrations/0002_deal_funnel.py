# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='deal',
            name='funnel',
            field=models.ForeignKey(verbose_name='funnel', related_name='deals', default=0, to='deals.Funnel'),
            preserve_default=False,
        ),
    ]
