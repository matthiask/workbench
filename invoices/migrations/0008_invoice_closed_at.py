# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0007_auto_20150320_1534'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='closed_at',
            field=models.DateTimeField(null=True, verbose_name='closed at', blank=True),
        ),
    ]
