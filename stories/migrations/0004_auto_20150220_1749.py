# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0003_auto_20150220_1746'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requiredservice',
            name='effort_best_case',
            field=models.DecimalField(max_digits=5, help_text='Hours required if everything falls into place.', verbose_name='best case effort', decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='requiredservice',
            name='effort_safe_case',
            field=models.DecimalField(max_digits=5, help_text='Hours required to be almost certain that the work will be completed.', verbose_name='safe case effort', decimal_places=2),
            preserve_default=True,
        ),
    ]
