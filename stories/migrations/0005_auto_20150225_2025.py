# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0004_auto_20150220_1749'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='requiredservice',
            name='effort_best_case',
        ),
        migrations.RemoveField(
            model_name='requiredservice',
            name='effort_safe_case',
        ),
        migrations.AddField(
            model_name='requiredservice',
            name='estimated_effort',
            field=models.DecimalField(decimal_places=2, default=0, verbose_name='estimated effort', max_digits=5, help_text='The original estimate.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='requiredservice',
            name='offered_effort',
            field=models.DecimalField(decimal_places=2, default=0, verbose_name='offered effort', max_digits=5, help_text='Effort offered to the customer.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='requiredservice',
            name='planning_effort',
            field=models.DecimalField(decimal_places=2, default=0, verbose_name='planning effort', max_digits=5, help_text='Effort for planning. This value should reflect the current  state of affairs also when work is already in progress.'),
            preserve_default=False,
        ),
    ]
