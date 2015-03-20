# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0004_auto_20150320_1507'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offer',
            name='tax_rate',
            field=models.DecimalField(decimal_places=2, verbose_name='tax rate', max_digits=10, default=8),
        ),
    ]
